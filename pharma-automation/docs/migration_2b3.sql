-- ============================================================================
-- Phase 2B-3: Narcotics Inventory/Transaction CRUD - Migration
-- ============================================================================

-- 1a. Add version column for optimistic locking
ALTER TABLE narcotics_inventory
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

-- 1b. Add is_active column for soft delete
ALTER TABLE narcotics_inventory
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 1c. Expand transaction_type CHECK to include RETURN
ALTER TABLE narcotics_transactions
    DROP CONSTRAINT narcotics_transactions_transaction_type_check;
ALTER TABLE narcotics_transactions
    ADD CONSTRAINT narcotics_transactions_transaction_type_check
    CHECK (transaction_type IN ('RECEIVE', 'DISPENSE', 'DISPOSE', 'ADJUST', 'RETURN'));

-- 1d. Expand inventory_audit_log action CHECK for narcotics actions
ALTER TABLE inventory_audit_log
    DROP CONSTRAINT inventory_audit_log_action_check;
ALTER TABLE inventory_audit_log
    ADD CONSTRAINT inventory_audit_log_action_check
    CHECK (action IN ('INSERT', 'UPDATE', 'DELETE', 'OTC_DELETE', 'NARCOTICS_DEACTIVATE'));
