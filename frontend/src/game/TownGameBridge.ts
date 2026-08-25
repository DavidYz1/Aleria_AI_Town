import type {
  NpcVisualProjection,
  TownGameInput,
} from './contracts'


type BridgeListener<T> = (payload: T) => void

export class TownGameBridge {
  private input: TownGameInput
  private readonly npcsUpdatedListeners = new Set<
    BridgeListener<NpcVisualProjection[]>
  >()
  private readonly npcSelectedListeners = new Set<BridgeListener<string>>()
  private readonly playerLocationEnteredListeners = new Set<BridgeListener<string>>()
  private readonly playerTeleportListeners = new Set<BridgeListener<string>>()
  private readonly loadFailedListeners = new Set<BridgeListener<string>>()

  constructor(input: TownGameInput) {
    this.input = copyInput(input)
  }

  getInput(): TownGameInput {
    return copyInput(this.input)
  }

  updateNpcs(npcs: NpcVisualProjection[]): void {
    this.input = { ...this.input, npcs: copyNpcs(npcs) }
    for (const listener of [...this.npcsUpdatedListeners]) {
      listener(copyNpcs(this.input.npcs))
    }
  }

  onNpcsUpdated(
    listener: BridgeListener<NpcVisualProjection[]>,
  ): () => void {
    this.npcsUpdatedListeners.add(listener)
    return () => this.npcsUpdatedListeners.delete(listener)
  }

  emitNpcSelected(npcId: string): void {
    for (const listener of [...this.npcSelectedListeners]) listener(npcId)
  }

  onNpcSelected(listener: BridgeListener<string>): () => void {
    this.npcSelectedListeners.add(listener)
    return () => this.npcSelectedListeners.delete(listener)
  }

  emitPlayerLocationEntered(locationId: string): void {
    for (const listener of [...this.playerLocationEnteredListeners]) {
      listener(locationId)
    }
  }

  onPlayerLocationEntered(
    listener: BridgeListener<string>,
  ): () => void {
    this.playerLocationEnteredListeners.add(listener)
    return () => this.playerLocationEnteredListeners.delete(listener)
  }

  teleportPlayer(locationId: string): void {
    this.input = { ...this.input, playerLocationId: locationId }
    for (const listener of [...this.playerTeleportListeners]) listener(locationId)
  }

  onPlayerTeleport(listener: BridgeListener<string>): () => void {
    this.playerTeleportListeners.add(listener)
    return () => this.playerTeleportListeners.delete(listener)
  }

  emitLoadFailed(message: string): void {
    for (const listener of [...this.loadFailedListeners]) listener(message)
  }

  onLoadFailed(listener: BridgeListener<string>): () => void {
    this.loadFailedListeners.add(listener)
    return () => this.loadFailedListeners.delete(listener)
  }

  clear(): void {
    this.npcsUpdatedListeners.clear()
    this.npcSelectedListeners.clear()
    this.playerLocationEnteredListeners.clear()
    this.playerTeleportListeners.clear()
    this.loadFailedListeners.clear()
  }
}

function copyInput(input: TownGameInput): TownGameInput {
  return {
    profile: { ...input.profile },
    playerLocationId: input.playerLocationId,
    npcs: copyNpcs(input.npcs),
  }
}

function copyNpcs(npcs: readonly NpcVisualProjection[]): NpcVisualProjection[] {
  return npcs.map((npc) => ({ ...npc }))
}
