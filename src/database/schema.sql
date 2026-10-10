CREATE TABLE categorias (
    
    id     INT AUTO_INCREMENT PRIMARY KEY,
    nome   VARCHAR(60) NOT NULL UNIQUE,
    tipo   ENUM('entrada','saida') NOT NULL,
    ativa  TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE contas (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    nome           VARCHAR(60) NOT NULL UNIQUE,
    tipo           ENUM('carteira','corrente','poupanca','cartao') NOT NULL,
    saldo_inicial  BIGINT NOT NULL DEFAULT 0          -- em centavos
) ENGINE=InnoDB;

CREATE TABLE transacoes (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    data             DATE NOT NULL,
    valor            BIGINT NOT NULL,                  -- em centavos
    tipo             ENUM('entrada','saida') NOT NULL,
    categoria_id     INT NOT NULL,
    conta_id         INT NOT NULL,
    descricao        VARCHAR(255),
    forma_pagamento  ENUM('pix','debito','credito','dinheiro','outro'),
    criado_em        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_transacoes_valor CHECK (valor > 0),
    CONSTRAINT fk_transacoes_categoria FOREIGN KEY (categoria_id) REFERENCES categorias(id),
    CONSTRAINT fk_transacoes_conta FOREIGN KEY (conta_id) REFERENCES contas(id),
    INDEX idx_transacoes_data (data)
) ENGINE=InnoDB;

CREATE TABLE orcamentos (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    categoria_id  INT NOT NULL,
    mes           CHAR(7) NOT NULL,                    -- 'AAAA-MM'
    limite        BIGINT NOT NULL,                     -- em centavos
    UNIQUE (categoria_id, mes),
    CONSTRAINT fk_orcamentos_categoria FOREIGN KEY (categoria_id) REFERENCES categorias(id)
) ENGINE=InnoDB;

CREATE TABLE metas (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    nome                VARCHAR(100) NOT NULL,         -- ex.: Reserva de emergência
    valor_alvo          BIGINT NOT NULL,
    prazo               DATE NULL,
    percentual_entrada  DECIMAL(5,2) NOT NULL DEFAULT 0  -- % de cada entrada a separar
) ENGINE=InnoDB;

CREATE TABLE aportes_meta (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    meta_id  INT NOT NULL,
    data     DATE NOT NULL,
    valor    BIGINT NOT NULL,
    CONSTRAINT fk_aportes_meta FOREIGN KEY (meta_id) REFERENCES metas(id)
) ENGINE=InnoDB;
