CREATE DATABASE IF NOT EXISTS safe_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

-- IDENTIFIED BY 값은 .env 의 DB_PASSWORD 와 동일하게 설정하세요.
CREATE USER IF NOT EXISTS 'safe_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';
GRANT ALL PRIVILEGES ON safe_db.* TO 'safe_user'@'localhost';
FLUSH PRIVILEGES;
