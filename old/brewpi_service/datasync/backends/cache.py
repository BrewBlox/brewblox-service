from collections import defaultdict
from datetime import datetime, timedelta


class AvailableControllerBlocksCache:
    """
    Cache the available blocks, in-memory.
    """
    def __init__(self):
        self._blocks = defaultdict(dict)

    def _hash_for(self, aControllerBlock):
        return hash((aControllerBlock.object_id,))

    def add(self, aController, aControllerBlock):
        block_hash = self._hash_for(aControllerBlock)

        if block_hash not in self._blocks[aController.uri].keys():
            self._blocks[aController.uri][block_hash] = aControllerBlock

        # If we already have this block in memory, mark it fresh
        self._blocks[aController.uri][block_hash].updated_at = datetime.utcnow()

    def remove(self, aController, aControllerBlock):
        block_hash = self._hash_for(aControllerBlock)

        if block_hash in self._blocks[aController.uri].keys():
            del self._blocks[aController.uri][block_hash]
            return True

        return False

    def get_all_for(self, aController):
        return self._blocks[aController.uri].values()

    def cleanup_stale_blocks_for(self, aController, timeout=timedelta(seconds=10)):
        """
        Remove all blocks that are outdated
        """
        now = datetime.utcnow()

        blocks_to_remove = []

        for block in self._blocks[aController.uri].values():
            if (now - block.updated_at) >= timeout:
                blocks_to_remove.append(block)

        for block in blocks_to_remove:
            self.remove(aController, block)




available_blocks_cache = AvailableControllerBlocksCache()
