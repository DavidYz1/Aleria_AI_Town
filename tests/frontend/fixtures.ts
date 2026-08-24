import type { NpcDetailData } from '../../frontend/src/types/npc'
import type { NpcChatData } from '../../frontend/src/types/chat'
import type { PlayerQuestData } from '../../frontend/src/types/playerQuest'
import type { WorldData } from '../../frontend/src/types/world'
import type { WorldTickData } from '../../frontend/src/types/worldTick'

export const worldFixture: WorldData = {
  world: { id: 'aleria-town', name: '曦谷', day: 1, time: '08:00', tick: 0 },
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
    world: { ...worldFixture.world, time: '09:00', tick: 1 },
    npcs: worldFixture.npcs.map((npc) => npc.id === 'shir'
      ? { ...npc, location_id: 'park', current_action: 'move', status: { energy: 65, mood: 64, social: 32 } }
      : npc),
  },
  actions: [
    { id: 1, tick: 1, actor_id: 'ryan', action_type: 'work', target_kind: null, target_id: null, reason: 'knight_training', status: 'recorded', world_time: '09:00' },
    { id: 2, tick: 1, actor_id: 'shir', action_type: 'move', target_kind: 'location', target_id: 'park', reason: 'low_social_find_companion', status: 'recorded', world_time: '09:00' },
    { id: 3, tick: 1, actor_id: 'grey', action_type: 'work', target_kind: null, target_id: null, reason: 'guardian_patrol', status: 'recorded', world_time: '09:00' },
  ],
  events: [
    { id: 1, tick: 1, event_type: 'npc_action', actor_id: 'ryan', action_id: 1, description: 'Ryan 工作', world_time: '09:00' },
    { id: 2, tick: 1, event_type: 'npc_action', actor_id: 'shir', action_id: 2, description: 'Shir 前往 park', world_time: '09:00' },
    { id: 3, tick: 1, event_type: 'npc_action', actor_id: 'grey', action_id: 3, description: 'Grey 工作', world_time: '09:00' },
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
    tick: 1,
    time_phase: 'morning',
  },
  recent_actions: [
    {
      id: 1,
      tick: 1,
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
