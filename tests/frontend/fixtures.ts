import type {
  NpcDetailData,
  NpcMemoryExplanationsData,
} from '../../frontend/src/types/npc'
import type { NpcChatData } from '../../frontend/src/types/chat'
import type { PlayerQuestData } from '../../frontend/src/types/playerQuest'
import type { WorldData } from '../../frontend/src/types/world'
import type { WorldTickData } from '../../frontend/src/types/worldTick'


class PhaserTestScene {
  constructor(_config?: unknown) {}
}

class PhaserTestGame {
  constructor(_config?: unknown) {}

  destroy(_removeCanvas?: boolean): void {}
}

const phaserTestStub = {
  AUTO: 0,
  Game: PhaserTestGame,
  Scene: PhaserTestScene,
  Scale: { RESIZE: 0, CENTER_BOTH: 0 },
  Scenes: { Events: { PAUSE: 'pause', SHUTDOWN: 'shutdown' } },
  Core: { Events: { BLUR: 'blur' } },
  Input: {
    Keyboard: {
      KeyCodes: {
        UP: 38,
        DOWN: 40,
        LEFT: 37,
        RIGHT: 39,
        W: 87,
        S: 83,
        A: 65,
        D: 68,
      },
    },
  },
}

export default phaserTestStub

export const worldFixture: WorldData = {
  world: {
    id: 'aleria-town', name: '曦谷', day: 1, time: '08:00',
    world_version: 0, clock_tick: 0, event_sequence: 0,
  },
  locations: [
    { id: 'tavern', name: '星辉酒馆', description: '炉火、消息与委托汇聚的温暖酒馆，许多旅人故事从这里开始' },
    { id: 'park', name: '中央公园', description: '居民散步与骑士训练的开阔绿地，日常生活掩映着战争旧痕' },
    { id: 'castle', name: '晨曦城堡', description: '守望曦谷的古老城堡，深处封存着灰烬战争留下的残缺档案' },
    { id: 'forest', name: '低语森林', description: '林间低语与古老遗迹交织的幽深森林，部分区域仍属于旧封锁线' },
  ],
  npcs: [
    {
      id: 'ryan', name: 'Ryan', role: 'Knight',
      personality: ['optimistic', 'brave', 'kind'], location_id: 'park',
      current_action: 'rest', status: { energy: 80, mood: 78, social: 70 },
    },
    {
      id: 'shir', name: 'Shir', role: 'Assassin',
      personality: ['quiet', 'introverted', 'observant'], location_id: 'tavern',
      current_action: 'eat', status: { energy: 72, mood: 65, social: 35 },
    },
    {
      id: 'grey', name: 'Grey', role: 'Guardian',
      personality: ['reliable', 'calm', 'protective'], location_id: 'castle',
      current_action: 'work', status: { energy: 88, mood: 74, social: 55 },
    },
  ],
}

export const tickFixture: WorldTickData = {
  world: {
    ...worldFixture,
    world: {
      ...worldFixture.world, time: '09:00',
      world_version: 1, clock_tick: 1, event_sequence: 3,
    },
    npcs: worldFixture.npcs.map((npc) => npc.id === 'shir'
      ? { ...npc, location_id: 'park', current_action: 'move', status: { energy: 65, mood: 64, social: 32 } }
      : npc),
  },
  run: {
    id: '00000000-0000-0000-0000-000000000001', mode: 'deterministic',
    trigger_type: 'world_advance', status: 'completed',
    base_world_version: 0, resulting_world_version: 1,
    base_clock_tick: 0, resulting_clock_tick: 1,
  },
  actions: [
    { id: 1, clock_tick: 1, actor_id: 'ryan', action_type: 'work', target_kind: null, target_id: null, reason: 'knight_training', status: 'executed', run_id: '00000000-0000-0000-0000-000000000001', proposal_id: 1, world_version: 1, world_time: '09:00' },
    { id: 2, clock_tick: 1, actor_id: 'shir', action_type: 'move', target_kind: 'location', target_id: 'park', reason: 'low_social_find_companion', status: 'executed', run_id: '00000000-0000-0000-0000-000000000001', proposal_id: 2, world_version: 1, world_time: '09:00' },
    { id: 3, clock_tick: 1, actor_id: 'grey', action_type: 'work', target_kind: null, target_id: null, reason: 'guardian_patrol', status: 'executed', run_id: '00000000-0000-0000-0000-000000000001', proposal_id: 3, world_version: 1, world_time: '09:00' },
  ],
  events: [
    { id: 1, run_id: '00000000-0000-0000-0000-000000000001', world_version: 1, clock_tick: 1, event_sequence: 1, event_type: 'npc_action', actor_id: 'ryan', action_id: 1, source_event_id: null, description: 'Ryan performed work', world_time: '09:00', payload: { action_type: 'work', target: null, reason_code: 'knight_training', proposal_ordinal: 0 }, visibility: 'public', secrecy: 'public', causation_id: null, correlation_id: '00000000-0000-0000-0000-000000000002', created_at: '2026-09-04T08:00:00Z' },
    { id: 2, run_id: '00000000-0000-0000-0000-000000000001', world_version: 1, clock_tick: 1, event_sequence: 2, event_type: 'npc_action', actor_id: 'shir', action_id: 2, source_event_id: null, description: 'Shir performed move', world_time: '09:00', payload: { action_type: 'move', target: { kind: 'location', id: 'park' }, reason_code: 'low_social_find_companion', proposal_ordinal: 1 }, visibility: 'public', secrecy: 'public', causation_id: null, correlation_id: '00000000-0000-0000-0000-000000000002', created_at: '2026-09-04T08:00:00Z' },
    { id: 3, run_id: '00000000-0000-0000-0000-000000000001', world_version: 1, clock_tick: 1, event_sequence: 3, event_type: 'npc_action', actor_id: 'grey', action_id: 3, source_event_id: null, description: 'Grey performed work', world_time: '09:00', payload: { action_type: 'work', target: null, reason_code: 'guardian_patrol', proposal_ordinal: 2 }, visibility: 'public', secrecy: 'public', causation_id: null, correlation_id: '00000000-0000-0000-0000-000000000002', created_at: '2026-09-04T08:00:00Z' },
  ],
}

export const npcDetailFixture: NpcDetailData = {
  profile: {
    id: 'ryan',
    name: 'Ryan',
    role: 'Knight',
    personality: ['optimistic', 'brave', 'kind'],
  },
  state: {
    location_id: 'park',
    location_name: '中央公园',
    current_action: 'work',
    status: {
      energy: 70,
      mood: 75,
      social: 67,
    },
  },
  world_context: {
    day: 1,
    time: '09:00',
    clock_tick: 1,
    time_phase: 'morning',
  },
  recent_actions: [
    {
      id: 1,
      clock_tick: 1,
      world_time: '09:00',
      action_type: 'work',
      target_kind: null,
      target_id: null,
      target_name: null,
      reason_code: 'knight_training',
      reason_text: '当前处于骑士训练时间，因此执行训练。',
    },
  ],
}

export const npcMemoryExplanationsFixture: NpcMemoryExplanationsData = {
  npc_id: 'ryan',
  retrieval_mode: 'hybrid',
  fallback_used: false,
  memories: [
    {
      id: 'a2f1c0d4-3b5e-4c77-9f1a-6d0b8e2c4517',
      type: 'episodic',
      summary: '在中央公园完成了一次骑士日常训练。',
      occurred_clock_tick: 1,
      source: { kind: 'world_event', label: '亲历事件' },
      reason_text: '这件事刚刚发生不久，这位居民印象还很清晰。',
    },
    {
      id: 'b7d3e910-8c42-4f6b-a05d-1e93f7c26840',
      type: 'knowledge',
      summary: 'Ryan 对自己的骑士职责有稳定认识。',
      occurred_clock_tick: 0,
      source: { kind: 'authored_knowledge', label: '稳定知识' },
      reason_text: '这件事对这位居民本人格外重要。',
    },
  ],
}

export const chatResponseFixture: NpcChatData = {
  conversation_id: '5e547c21-a228-4e86-940d-a1bf5d65702f',
  npc_id: 'ryan',
  turn: {
    user: {
      id: 1,
      role: 'user',
      content: '你害怕史莱姆吗？',
    },
    assistant: {
      id: 2,
      role: 'assistant',
      content: '害怕？当然不是……我只是觉得史莱姆比看起来更麻烦。',
      emotion: 'guarded',
    },
  },
  provider: 'mock',
  fallback_used: false,
}

export const availablePlayerQuestFixture: PlayerQuestData = {
  player: {
    id: 'default-player',
    location_id: 'tavern',
    location_name: '星辉酒馆',
  },
  quest: {
    id: 'missing-child',
    title: '失踪的孩子',
    status: 'available',
    version: 0,
    objective: '查看星辉酒馆告示板上的失踪委托。',
    available_interactions: [
      { id: 'accept_quest', label: '接受委托' },
    ],
    recent_events: [],
  },
}

export const acceptedPlayerQuestFixture: PlayerQuestData = {
  player: {
    id: 'default-player',
    location_id: 'castle',
    location_name: '晨曦城堡',
  },
  quest: {
    id: 'missing-child',
    title: '失踪的孩子',
    status: 'accepted',
    version: 1,
    objective: '前往晨曦城堡询问 Grey。',
    available_interactions: [
      { id: 'ask_grey', label: '询问 Grey' },
    ],
    recent_events: [
      {
        id: 1,
        from_status: 'available',
        to_status: 'accepted',
        interaction: 'accept_quest',
        description: '你在星辉酒馆接受了寻找失踪孩子的委托。',
      },
    ],
  },
}
