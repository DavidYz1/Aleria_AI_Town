import type { WorldData } from '../../frontend/src/types/world'

export const worldFixture: WorldData = {
  world: {
    id: 'aleria-town',
    name: '晨曦镇',
    day: 1,
    time: '08:00',
    tick: 0,
  },
  locations: [
    {
      id: 'tavern',
      name: '星辰酒馆',
      description: '冒险者交流和休息的地方',
    },
    {
      id: 'park',
      name: '中央公园',
      description: '居民散步和放松的地方',
    },
  ],
  npcs: [
    {
      id: 'ryan',
      name: 'Ryan',
      role: 'Knight',
      personality: ['optimistic', 'brave', 'kind'],
      location_id: 'park',
      current_action: 'rest',
      status: { energy: 80, mood: 78, social: 70 },
    },
    {
      id: 'shir',
      name: 'Shir',
      role: 'Assassin',
      personality: ['quiet', 'introverted', 'observant'],
      location_id: 'tavern',
      current_action: 'eat',
      status: { energy: 72, mood: 65, social: 35 },
    },
    {
      id: 'grey',
      name: 'Grey',
      role: 'Guardian',
      personality: ['reliable', 'calm', 'protective'],
      location_id: 'park',
      current_action: 'work',
      status: { energy: 88, mood: 74, social: 55 },
    },
  ],
}
