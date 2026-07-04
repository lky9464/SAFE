-- SAFE MariaDB 최초 환경: 계정 생성
-- IDENTIFIED BY 값은 .env 의 DB_PASSWORD 와 동일하게 설정하세요.
DROP USER IF EXISTS 'safe_user'@'localhost';
CREATE USER 'safe_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';
GRANT ALL PRIVILEGES ON safe_db.* TO 'safe_user'@'localhost';
FLUSH PRIVILEGES;
SELECT user, host FROM mysql.user WHERE user = 'safe_user';
SHOW GRANTS FOR 'safe_user'@'localhost';
