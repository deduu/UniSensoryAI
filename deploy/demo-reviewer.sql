-- Explicitly enable PAPER decisions for the shared demo identity after migrations.
-- Only use on the dedicated demo database. No password is stored in this row.
BEGIN;

INSERT INTO users
    (id, tenant_id, email, name, oauth_provider, oauth_subject, role, created_at)
VALUES
    ('dev-user', 'default', 'demo-admin@example.invalid', 'Demo reviewer',
     'shared-demo', 'dev-user', 'accountant', NOW())
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = 'dev-user' AND tenant_id = 'default'
          AND oauth_provider = 'shared-demo' AND role = 'accountant'
    ) THEN
        RAISE EXCEPTION 'Existing dev-user does not match the shared reviewer; inspect before changing it';
    END IF;
END;
$$;

COMMIT;
