PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS waves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL,
    date_debut  DATE NOT NULL,
    date_fin    DATE NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'brouillon' CHECK (statut IN ('brouillon', 'active', 'cloturee'))
);

-- Une seule vague active à la fois — filet de sécurité en base, en plus du
-- contrôle applicatif fait dans /vague-activer.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_wave
    ON waves((1))
    WHERE statut = 'active';

CREATE TABLE IF NOT EXISTS members (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id        TEXT NOT NULL,
    nom               TEXT NOT NULL,
    profil            TEXT NOT NULL CHECK (profil IN ('étudiant', 'demandeur d''emploi', 'cadre', 'alternant', 'autre')),
    certif_ou_projet  TEXT,
    objectif_vague    TEXT,
    wave_id           INTEGER NOT NULL REFERENCES waves(id),
    UNIQUE (discord_id, wave_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    wave_id     INTEGER NOT NULL REFERENCES waves(id),
    semaine     INTEGER NOT NULL,
    date        DATE NOT NULL,
    creneau     TEXT NOT NULL CHECK (creneau IN ('5h-7h', '19h-21h', '21h-23h')),
    canal_id    TEXT,
    canal_nom   TEXT,
    debut       DATETIME NOT NULL,
    fin         DATETIME,
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
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    wave_id   INTEGER NOT NULL REFERENCES waves(id),
    semaine   INTEGER NOT NULL,
    membre_a  INTEGER NOT NULL REFERENCES members(id),
    membre_b  INTEGER NOT NULL REFERENCES members(id)
);

CREATE TABLE IF NOT EXISTS coworking_channels (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    canal_id   TEXT NOT NULL UNIQUE,
    canal_nom  TEXT NOT NULL,
    actif      BOOLEAN NOT NULL DEFAULT 1
);
