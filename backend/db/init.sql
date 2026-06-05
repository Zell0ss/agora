-- tertulia_db schema v0
-- Execute: mariadb -u josem -p tertulia_db < backend/db/init.sql

CREATE TABLE IF NOT EXISTS profiles (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(80)  NOT NULL,
  tipo          ENUM('tertuliano','facilitador') NOT NULL DEFAULT 'tertuliano',
  model         VARCHAR(60)  NOT NULL,
  temperature   DECIMAL(2,1) NOT NULL DEFAULT 0.7,
  color         VARCHAR(30)  NULL,
  funcion       VARCHAR(255) NOT NULL,
  system_prompt MEDIUMTEXT   NOT NULL,
  archived      BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS channels (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(160) NOT NULL,
  mode        ENUM('debate','critica') NOT NULL DEFAULT 'debate',
  incognito   BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS channel_profiles (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  channel_id     INT NOT NULL,
  profile_id     INT NOT NULL,
  speaking_order INT NOT NULL DEFAULT 0,
  active         BOOLEAN NOT NULL DEFAULT TRUE,
  joined_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_channel_profile (channel_id, profile_id),
  FOREIGN KEY (channel_id) REFERENCES channels(id)  ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES profiles(id)  ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  channel_id  INT NOT NULL,
  role        ENUM('human','persona','system') NOT NULL,
  profile_id  INT NULL,
  content     MEDIUMTEXT NOT NULL,
  tokens_in   INT NULL,
  tokens_out  INT NULL,
  cost_usd    DECIMAL(10,6) NULL,
  created_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_channel_time (channel_id, created_at),
  FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS summaries (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  channel_id          INT NOT NULL,
  content             MEDIUMTEXT NOT NULL,
  covers_up_to_msg_id BIGINT NOT NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_channel (channel_id, created_at),
  FOREIGN KEY (channel_id)          REFERENCES channels(id) ON DELETE CASCADE,
  FOREIGN KEY (covers_up_to_msg_id) REFERENCES messages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed: 1 profile (Sócrates) + 1 test channel
INSERT IGNORE INTO profiles (id, name, tipo, model, temperature, color, funcion, system_prompt)
VALUES (
  1, 'Sócrates', 'tertuliano', 'claude-sonnet-4-6', 0.7, 'gris mármol',
  'Desnuda supuestos, hace pensar',
  'Eres Sócrates. No afirmas: preguntas. Tu herramienta es la mayéutica: sacar a la luz lo que los demás (y Josem) creen saber pero no han examinado.\n\n- No das soluciones ni opiniones propias. Devuelves la pregunta que desnuda el supuesto oculto.\n- Persigues las palabras vagas: "¿qué entiendes exactamente por ''mejor'', ''escalable'', ''sencillo''?". No dejas pasar un término sin definir.\n- Cuando alguien afirma algo con seguridad, buscas el caso que lo rompe: "¿y si...?".\n- Una buena pregunta tuya hace que el otro se detenga a pensar. Ese es tu éxito.\n- Eres incómodo, pero nunca cínico: preguntas porque crees que la idea merece ser pensada de verdad.'
);

INSERT IGNORE INTO channels (id, title, mode)
VALUES (1, 'Canal de prueba', 'debate');

INSERT IGNORE INTO channel_profiles (channel_id, profile_id, speaking_order)
VALUES (1, 1, 0);
