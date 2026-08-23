import type { WorldData } from '../../frontend/src/types/world'
import type { WorldTickData } from '../../frontend/src/types/worldTick'

export const worldFixture: WorldData = {
  world: { id: 'aleria-town', name: '晨曦镇', day: 1, time: '08:00', tick: 0 },
  locations: [
    { id: 'tavern', name: '星辰酒馆', description: '冒险者交流和休息的地方' },
    { id: 'park', name: '中央公园', description: '居民散步和放松的地方' },
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
      personality: ['reliable', 'calm', 'protective'], location_id: 'park',
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
    { id: 1, tick: 1, actor_id: 'ryan', action_type: 'work', target_kind: null, target_id: null, reason: 'knight_duty', status: 'recorded', world_time: '09:00' },
    { id: 2, tick: 1, actor_id: 'shir', action_type: 'move', target_kind: 'location', target_id: 'park', reason: 'low_social_find_companion', status: 'recorded', world_time: '09:00' },
    { id: 3, tick: 1, actor_id: 'grey', action_type: 'work', target_kind: null, target_id: null, reason: 'guardian_patrol', status: 'recorded', world_time: '09:00' },
  ],
  events: [
    { id: 1, tick: 1, event_type: 'npc_action', actor_id: 'ryan', action_id: 1, description: 'Ryan 工作', world_time: '09:00' },
    { id: 2, tick: 1, event_type: 'npc_action', actor_id: 'shir', action_id: 2, description: 'Shir 前往 park', world_time: '09:00' },
    { id: 3, tick: 1, event_type: 'npc_action', actor_id: 'grey', action_id: 3, description: 'Grey 工作', world_time: '09:00' },
  ],
}
