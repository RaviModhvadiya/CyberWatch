-- CyberWatch schema for XAMPP (MySQL / MariaDB). Run in phpMyAdmin > SQL.
CREATE DATABASE IF NOT EXISTS `cyberwatch` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `cyberwatch`;
SET FOREIGN_KEY_CHECKS = 0;

-- table detection_rules
CREATE TABLE IF NOT EXISTS detection_rules (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	`key` VARCHAR(40) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	severity VARCHAR(16) NOT NULL, 
	pattern TEXT, 
	threshold INTEGER, 
	window_seconds INTEGER, 
	description VARCHAR(255), 
	enabled BOOL NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table users
CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	active BOOL NOT NULL, 
	created_at DATETIME, 
	last_login DATETIME, 
	PRIMARY KEY (id),
	UNIQUE KEY `ix_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table activity_log
CREATE TABLE IF NOT EXISTS activity_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	action VARCHAR(40) NOT NULL, 
	detail VARCHAR(300), 
	ip VARCHAR(64), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id),
	KEY `ix_activity_log_action` (`action`),
	KEY `ix_activity_log_created_at` (`created_at`),
	KEY `ix_activity_log_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table reports
CREATE TABLE IF NOT EXISTS reports (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	dataset VARCHAR(20) NOT NULL, 
	fmt VARCHAR(10) NOT NULL, 
	row_count INTEGER, 
	generated_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id),
	KEY `ix_reports_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table uploaded_logs
CREATE TABLE IF NOT EXISTS uploaded_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	stored_name VARCHAR(300) NOT NULL, 
	log_type VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	total_entries INTEGER, 
	skipped_lines INTEGER, 
	alert_count INTEGER, 
	error VARCHAR(300), 
	upload_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id),
	KEY `ix_uploaded_logs_upload_date` (`upload_date`),
	KEY `ix_uploaded_logs_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table log_entries
CREATE TABLE IF NOT EXISTS log_entries (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	log_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	ip VARCHAR(64) NOT NULL, 
	timestamp DATETIME NOT NULL, 
	status_code INTEGER, 
	method VARCHAR(16), 
	request TEXT, 
	user_agent VARCHAR(255), 
	raw TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(log_id) REFERENCES uploaded_logs (id), 
	FOREIGN KEY(user_id) REFERENCES users (id),
	KEY `ix_log_entries_created_at` (`created_at`),
	KEY `ix_log_entries_ip` (`ip`),
	KEY `ix_log_entries_log_id` (`log_id`),
	KEY `ix_log_entries_status_code` (`status_code`),
	KEY `ix_log_entries_timestamp` (`timestamp`),
	KEY `ix_log_entries_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table alerts
CREATE TABLE IF NOT EXISTS alerts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	log_id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	ip VARCHAR(64) NOT NULL, 
	type VARCHAR(40) NOT NULL, 
	severity VARCHAR(16) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	description VARCHAR(400), 
	event_time DATETIME, 
	created_at DATETIME, 
	resolved_at DATETIME, 
	resolved_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(log_id) REFERENCES uploaded_logs (id), 
	FOREIGN KEY(entry_id) REFERENCES log_entries (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(resolved_by) REFERENCES users (id),
	KEY `ix_alerts_entry_id` (`entry_id`),
	KEY `ix_alerts_event_time` (`event_time`),
	KEY `ix_alerts_ip` (`ip`),
	KEY `ix_alerts_log_id` (`log_id`),
	KEY `ix_alerts_severity` (`severity`),
	KEY `ix_alerts_status` (`status`),
	KEY `ix_alerts_type` (`type`),
	KEY `ix_alerts_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table alert_notes
CREATE TABLE IF NOT EXISTS alert_notes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	alert_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	body TEXT, 
	status_to VARCHAR(20), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alert_id) REFERENCES alerts (id), 
	FOREIGN KEY(user_id) REFERENCES users (id),
	KEY `ix_alert_notes_alert_id` (`alert_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- default detection rules (edit later from Administration > Detection rules)
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'failed_login', 'Failed login', 'status', 'low', '', 1, 0, 'Every request answered with the configured failed-login status code.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'failed_login');
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'brute_force', 'Brute force', 'fail_burst', 'high', '', 5, 600, 'Repeated failed logins from one IP inside the time window.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'brute_force');
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'sql_injection', 'SQL injection', 'pattern', 'critical', '\\bunion\\b[\\s\\S]{0,30}\\bselect\\b\n\\bselect\\b[\\s\\S]{0,60}\\bfrom\\b\n[\'"]\\s*(or|and)\\s+[\'"\\d]\n\\b(or|and)\\b\\s+\\d+\\s*=\\s*\\d+\n\\b(drop|truncate)\\s+table\\b\n\\binsert\\s+into\\b\n\\bsleep\\s*\\(\\s*\\d+\n\\bwaitfor\\s+delay\\b\ninformation_schema\nxp_cmdshell\n;\\s*--', 1, 0, 'SQL keywords and tautologies inside request strings.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'sql_injection');
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'xss', 'Cross-site scripting', 'pattern', 'high', '<\\s*script\njavascript\\s*:\n\\bon(error|load|click|mouseover|focus)\\s*=\n<\\s*(iframe|svg|img)[^>]*(src|onload|onerror)\ndocument\\.(cookie|location)\n\\balert\\s*\\(', 1, 0, 'Script tags, event handlers and cookie access in request strings.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'xss');
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'directory_traversal', 'Directory traversal', 'pattern', 'high', '\\.\\./\n\\.\\.\\\\\n%2e%2e\n/etc/(passwd|shadow)\n\\b(boot|win)\\.ini\\b\nc:\\\\windows', 1, 0, 'Parent-directory jumps and requests for sensitive system files.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'directory_traversal');
INSERT INTO `detection_rules` (`key`, `name`, `kind`, `severity`, `pattern`, `threshold`, `window_seconds`, `description`, `enabled`) SELECT 'dos', 'High request rate (DoS)', 'rate', 'critical', '', 100, 60, 'One IP sending too many requests inside the time window.', 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `detection_rules` WHERE `key` = 'dos');

-- first administrator: admin@cyberwatch.local / Admin@12345 (change it after signing in)
INSERT INTO `users` (`name`, `email`, `password_hash`, `role`, `active`, `created_at`) SELECT 'System Administrator', 'admin@cyberwatch.local', 'scrypt:32768:8:1$hgLg98J4idYmXBIW$2f7e72531c09f02c61d78fbe1fd7d9cf8ac818ef52dffd6c8fa6f287b26989a5be522dd870e86f1d6395554e17f2f41b0e5a755bb2c8173768a3db0d90812ae9', 'admin', 1, NOW() FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `users` WHERE `email` = 'admin@cyberwatch.local');
