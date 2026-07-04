-- SAFE MariaDB 최초 환경: 기존 DB 초기화 후 재생성
DROP DATABASE IF EXISTS safe_db;
CREATE DATABASE safe_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
