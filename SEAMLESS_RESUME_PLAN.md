# Seamless Task Resume & Incremental Saving Plan

## 1. Objective
Enable tasks to be suspended (due to network error, manual stop, etc.) and resumed seamlessly without data loss or duplication.
Specifically for the **Structure Phase (Agent A)**, which currently holds data in memory until completion.

## 2. Current Limitation
- **Structure Phase**: Entities are extracted chunk by chunk but stored in a list `all_entities_data`. They are only written to the DB after *all* chunks are processed.
- **Consequence**: If a task fails at Chunk 171/358, the work for the first 171 chunks is lost. Resuming requires restarting from Chunk 1.

## 3. Proposed Solution

### A. Database Schema Change
Add a `progress` column to the `sys_tasks` table to track the state of processing.

```python
class SysTask(Base):
    # ...
    progress = Column(Text, nullable=True) # JSON: {"phase": "STRUCTURE", "chunk_index": 171, "total_chunks": 358}
```

### B. Orchestrator Logic Update (Structure Phase)
Refactor `process_task` to support **Incremental Saving** and **Checkpointing**.

**New Workflow:**
1. **Initialization**:
   - Load `task.progress`.
   - If `progress` indicates we are in `STRUCTURE` phase, read `last_chunk_index`.
   - Re-chunk the text (requires deterministic chunking).

2. **Processing Loop**:
   - Iterate through chunks.
   - **Skip Condition**: If `current_chunk_index <= last_chunk_index`, skip this chunk (already processed).
   - **Processing**: Call Agent A as usual.
   - **Incremental Save**:
     - Immediately call `_save_entity_recursive` for the extracted entities.
     - Append new Global Tips to `task.global_context_tips`.
   - **Update Progress**:
     - Update `task.progress = {"phase": "STRUCTURE", "chunk_index": current_index}`.
     - Commit DB transaction.

3. **Completion**:
   - Mark phase as `EXTRACTING`.
   - Clear or update `progress`.

### C. API Update
- **`resume_task`**:
  - Remove the logic that wipes existing entities (since we now want to keep them).
  - Ensure `target_files` are read correctly (already fixed).
  - Set status to `PENDING` so Orchestrator picks it up.

## 4. Benefits
- **No Data Loss**: Data is saved every few seconds (per chunk).
- **Efficiency**: Resuming skips already processed work.
- **Safety**: "Get or Create" logic in `_save_entity_recursive` ensures idempotency (no duplicates even if a chunk is partially re-processed).

## 5. Migration
- Requires adding `progress` column to `sys_tasks`.
- SQL: `ALTER TABLE sys_tasks ADD COLUMN progress TEXT;`
