-- Schéma PostgreSQL (Neon) — utilisé par le bot (dev/prod, bot/db/database.py)
-- et par la suite de tests (tests/conftest.py), qui tourne aussi sur Postgres
-- dans une transaction annulée à chaque test.
--
-- Dates/horodatages gardés en TEXT (ISO 8601) plutôt qu'en DATE/TIMESTAMPTZ,
-- pour rester compatibles avec le code applicatif qui parse via
-- datetime.fromisoformat().

CREATE TABLE IF NOT EXISTS waves (
    id          SERIAL PRIMARY KEY,
    nom         TEXT NOT NULL,
    date_debut  TEXT NOT NULL,
    date_fin    TEXT NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'brouillon' CHECK (statut IN ('brouillon', 'active', 'cloturee'))
);

-- Une seule vague active à la fois — filet de sécurité en base, en plus du
-- contrôle applicatif fait dans /vague-activer.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_wave
    ON waves((1))
    WHERE statut = 'active';

CREATE TABLE IF NOT EXISTS members (
    id                SERIAL PRIMARY KEY,
    discord_id        TEXT NOT NULL,
    nom               TEXT NOT NULL,
    profil            TEXT NOT NULL CHECK (profil IN ('étudiant', 'demandeur d''emploi', 'cadre', 'alternant', 'autre')),
    certif_ou_projet  TEXT,
    objectif_vague    TEXT,
    thread_objectif_id TEXT,
    wave_id           INTEGER NOT NULL REFERENCES waves(id),
    UNIQUE (discord_id, wave_id)
);

-- Migration pour les bases déjà créées avant l'ajout de la colonne (RG forum objectifs).
ALTER TABLE members ADD COLUMN IF NOT EXISTS thread_objectif_id TEXT;

CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    wave_id     INTEGER NOT NULL REFERENCES waves(id),
    semaine     INTEGER NOT NULL,
    date        TEXT NOT NULL,
    creneau     TEXT NOT NULL CHECK (creneau IN ('5h-7h', '19h-21h', '21h-23h')),
    canal_id    TEXT,
    canal_nom   TEXT,
    debut       TEXT NOT NULL,
    fin         TEXT,
    objectif    TEXT NOT NULL,
    bilan       TEXT,
    blocages    TEXT,
    statut      TEXT NOT NULL DEFAULT 'ouverte' CHECK (statut IN ('ouverte', 'complète', 'incomplète'))
);

-- RG-02 : une seule session ouverte (fin IS NULL) par membre — filet de sécurité en base,
-- en plus du contrôle applicatif fait au niveau du cog.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_session
    ON sessions(member_id)
    WHERE fin IS NULL;

CREATE TABLE IF NOT EXISTS binomes (
    id        SERIAL PRIMARY KEY,
    wave_id   INTEGER NOT NULL REFERENCES waves(id),
    semaine   INTEGER NOT NULL,
    membre_a  INTEGER NOT NULL REFERENCES members(id),
    membre_b  INTEGER NOT NULL REFERENCES members(id)
);

-- Table de jonction : un membre ne peut appartenir qu'à un seul binôme par
-- (vague, semaine) — filet de sécurité en base, même logique que RG-02 sur sessions.
CREATE TABLE IF NOT EXISTS binome_membres (
    id         SERIAL PRIMARY KEY,
    binome_id  INTEGER NOT NULL REFERENCES binomes(id),
    member_id  INTEGER NOT NULL REFERENCES members(id),
    wave_id    INTEGER NOT NULL REFERENCES waves(id),
    semaine    INTEGER NOT NULL,
    UNIQUE (member_id, wave_id, semaine)
);

-- Un salon est rattaché à une vague précise (un même salon vocal peut être
-- réutilisé d'une vague à l'autre, mais chaque vague a sa propre liste).
CREATE TABLE IF NOT EXISTS coworking_channels (
    id         SERIAL PRIMARY KEY,
    canal_id   TEXT NOT NULL,
    canal_nom  TEXT NOT NULL,
    actif      BOOLEAN NOT NULL DEFAULT TRUE,
    wave_id    INTEGER NOT NULL REFERENCES waves(id),
    UNIQUE (canal_id, wave_id)
);

-- Migration pour les bases créées avant le rattachement des salons à une vague
-- (2026-08-14) : les salons existants sont rattachés à la vague active.
ALTER TABLE coworking_channels ADD COLUMN IF NOT EXISTS wave_id INTEGER REFERENCES waves(id);
UPDATE coworking_channels SET wave_id = (SELECT id FROM waves WHERE statut = 'active' LIMIT 1) WHERE wave_id IS NULL;
ALTER TABLE coworking_channels ALTER COLUMN wave_id SET NOT NULL;
ALTER TABLE coworking_channels DROP CONSTRAINT IF EXISTS coworking_channels_canal_id_key;
ALTER TABLE coworking_channels DROP CONSTRAINT IF EXISTS coworking_channels_canal_id_wave_id_key;
ALTER TABLE coworking_channels ADD CONSTRAINT coworking_channels_canal_id_wave_id_key UNIQUE (canal_id, wave_id);
