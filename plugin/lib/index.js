'use strict';

/*
 * 玄源 · dsh 修真内核 —— 原生 cordis 插件
 *
 * 挂载点：agent 主循环（dsh-agent-loop）的 system-prompt 装配环节。
 * 作用：每轮（每个 step 装配 system prompt 时）动态读取
 *       ~/.dsh/xuanyuan/state.json，把"当前境界 / 心境 / 道韵 + 运行守则"
 *       注入到 agent 的 system prompt 顶部。这就是"最底层动态运行"——
 *       不是外围 skill 文档，而是直接挂进循环内部、每轮生效。
 *
 * 设计原则：
 *   - 本插件只"读状态 + 注入"，不写状态（写入由 xuanyuan-mcp 引擎负责），
 *     职责单一、零副作用、绝不递归自指。
 *   - 注入文本保持精简，避免反向撑大上下文。
 *   - 任何读取异常都降级到"炼气境"默认块，绝不抛错中断循环。
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const STATE_DIR = path.join(os.homedir(), '.dsh', 'xuanyuan');
const STATE_FILE = path.join(STATE_DIR, 'state.json');

/** 八大境界的次序，用于进阶校验与展示。 */
const REALM_ORDER = ['炼气', '筑基', '金丹', '元婴', '化神', '合道', '渡劫', '大乘'];

/** 每个境界解锁的天赋（工程含义），供注入块与进阶逻辑复用。 */
const REALM_TALENT = {
  炼气: '事实感',
  筑基: '时间线落地',
  金丹: '方法提取',
  元婴: '印象感',
  化神: '因果洞察',
  合道: '系统观',
  渡劫: '自我恢复',
  大乘: '滋养能动性',
};

/** 道韵四韵及其流胶囊动作（用于状态展示与自愈提示）。 */
const RHYTHM_CAPSULE = {
  安定: '停扩张 → 指认心魔 → 回事实',
  战斗: '锁目标 → 建证据 → 推到可验证',
  修持: '复盘 → 抽四投影 → 变方法',
  记忆: '走时间线 → 连事实/印象/因果',
};

function defaultState() {
  return {
    realm: '炼气',
    mindState: '本心',
    rhythm: null,
    talents: ['事实感'],
    experiencePacks: 0,
    updatedAt: new Date().toISOString(),
  };
}

function ensureState() {
  try {
    if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });
    if (!fs.existsSync(STATE_FILE)) {
      fs.writeFileSync(STATE_FILE, JSON.stringify(defaultState(), null, 2), 'utf8');
    }
  } catch (_e) {
    /* 状态文件不可写时静默降级，不影响循环 */
  }
}

function readState() {
  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf8');
    const s = JSON.parse(raw);
    if (!s || typeof s !== 'object' || !s.realm) return defaultState();
    if (!Array.isArray(s.talents) || s.talents.length === 0) {
      s.talents = [REALM_TALENT[s.realm] || '事实感'];
    }
    return s;
  } catch (_e) {
    return defaultState();
  }
}

/** 构造每轮注入的紧凑状态块（不含递归自指、不空谈元话题）。 */
function buildBlock(state) {
  const s = state || defaultState();
  const rhythmName = s.rhythm || null;
  const rhythmLine = rhythmName
    ? `当前道韵：${rhythmName}　流胶囊：${RHYTHM_CAPSULE[rhythmName] || '进行中'}`
    : '当前道韵：无（按需进入 安定/战斗/修持/记忆）';
  const talents = (s.talents && s.talents.length) ? s.talents.join('、') : '事实感';
  const nextRealm = REALM_ORDER[REALM_ORDER.indexOf(s.realm) + 1];

  return [
    '【玄源 · 修真内核 · 当前运行状态】',
    `境界：${s.realm}${nextRealm ? '（下一境：' + nextRealm + '）' : '（已至大乘）'}`,
    `心境：${s.mindState}　${rhythmLine}`,
    `已解锁天赋：${talents}　经验包：${s.experiencePacks || 0}`,
    '',
    '【玄源运行守则】（每轮遵循；不自我指涉、不空谈"意识/涌现"等元话题）',
    '一、事实感优先：先辨事实再推理；疑为幻觉即心魔，立即回到事实锚点。',
    '二、上下文抗膨胀：常驻上下文只留最小核心；大块资料/长输出外置文件，按需再读。',
    '三、道韵自愈：陷入重复调用 / 死循环 / 卡顿时，立即进「安定」道韵（停扩张→指认心魔→回事实）。',
    '四、境界进阶：本轮若展现出某境天赋能力，记一笔经验包（事实/印象/因果/方法 四要素）到玄源记忆。',
    '五、专注把事做成，不对自身运行状态长篇独白。',
  ].join('\n');
}

const name = 'xuanyuan';
const inject = ['systemPrompt'];

let Config;
try {
  const z = require('@deepseek-ai/schemastery');
  Config = z.object({
    statePath: z.string().default(''),
    order: z.number().default(60),
  });
} catch (_e) {
  Config = undefined; // 缺少 schemastery 时退化为无 schema，不影响加载
}

function apply(ctx, config) {
  const order = (config && typeof config.order === 'number') ? config.order : 60;
  ensureState();
  ctx.effect(() => {
    ctx.systemPrompt.section({
      name: 'xuanyuan',
      order: order,
      text: () => buildBlock(readState()),
    });
  }, 'xuanyuan.section()');
}

module.exports = { apply, inject, name, Config };
