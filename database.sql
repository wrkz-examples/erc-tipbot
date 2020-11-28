SET NAMES utf8;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;
SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';

DROP TABLE IF EXISTS `bot_tipnotify_user`;
CREATE TABLE `bot_tipnotify_user` (
  `user_id` varchar(32) NOT NULL,
  `date` int(11) NOT NULL,
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;


SET NAMES utf8mb4;

DROP TABLE IF EXISTS `erc_contract`;
CREATE TABLE `erc_contract` (
  `http_address` varchar(128) NOT NULL,
  `token_name` varchar(16) NOT NULL,
  `contract` varchar(128) NOT NULL,
  `token_decimal` tinyint(3) NOT NULL,
  `real_min_tip` float NOT NULL,
  `real_max_tip` float NOT NULL,
  `real_min_tx` float NOT NULL,
  `real_max_tx` float NOT NULL,
  `real_min_deposit` float NOT NULL,
  `real_deposit_fee` float NOT NULL,
  `deposit_confirm_depth` int(4) NOT NULL,
  `real_withdraw_fee` float NOT NULL,
  `withdraw_address` varchar(128) NOT NULL,
  `enable_tip` enum('YES','NO') NOT NULL DEFAULT 'NO',
  `enable_deposit` enum('YES','NO') NOT NULL DEFAULT 'NO',
  `enable_withdraw` enum('YES','NO') NOT NULL DEFAULT 'NO',
  UNIQUE KEY `token_name` (`token_name`),
  UNIQUE KEY `contract` (`contract`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `erc_external_tx`;
CREATE TABLE `erc_external_tx` (
  `token_name` varchar(32) NOT NULL,
  `contract` varchar(128) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `real_amount` float NOT NULL,
  `real_external_fee` float NOT NULL,
  `token_decimal` tinyint(3) NOT NULL,
  `to_address` varchar(128) NOT NULL,
  `date` int(11) NOT NULL,
  `txn` varchar(128) NOT NULL,
  `user_server` enum('DISCORD','TELEGRAM') CHARACTER SET ascii NOT NULL DEFAULT 'DISCORD',
  KEY `token_name` (`token_name`),
  KEY `user_id` (`user_id`),
  KEY `user_server` (`user_server`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


DROP TABLE IF EXISTS `erc_move_deposit`;
CREATE TABLE `erc_move_deposit` (
  `token_name` varchar(16) NOT NULL,
  `contract` varchar(128) DEFAULT NULL,
  `user_id` varchar(32) NOT NULL,
  `balance_wallet_address` varchar(128) NOT NULL,
  `to_main_address` varchar(128) NOT NULL,
  `real_amount` float NOT NULL,
  `real_deposit_fee` float NOT NULL,
  `token_decimal` tinyint(3) NOT NULL,
  `txn` varchar(128) NOT NULL,
  `blockNumber` int(11) DEFAULT NULL,
  `confirmed_depth` int(4) NOT NULL DEFAULT 0,
  `status` enum('PENDING','CONFIRMED') NOT NULL DEFAULT 'PENDING',
  `time_insert` int(11) NOT NULL,
  `notified_confirmation` enum('YES','NO') NOT NULL DEFAULT 'NO',
  `failed_notification` enum('YES','NO') NOT NULL DEFAULT 'NO',
  `time_notified` int(11) DEFAULT NULL,
  `user_server` enum('DISCORD','TELEGRAM') NOT NULL DEFAULT 'DISCORD',
  UNIQUE KEY `txn` (`txn`),
  KEY `token_name` (`token_name`),
  KEY `user_id` (`user_id`),
  KEY `status` (`status`),
  KEY `confirmed_depth` (`confirmed_depth`),
  KEY `notified_confirmation` (`notified_confirmation`),
  KEY `failed_notification` (`failed_notification`),
  KEY `contract` (`contract`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


DROP TABLE IF EXISTS `erc_mv_tx`;
CREATE TABLE `erc_mv_tx` (
  `token_name` varchar(16) NOT NULL,
  `contract` varchar(128) NOT NULL,
  `from_userid` varchar(32) NOT NULL,
  `to_userid` varchar(32) NOT NULL,
  `real_amount` float NOT NULL,
  `token_decimal` tinyint(3) NOT NULL,
  `type` enum('TIP','TIPS','TIPALL','DONATE','SECRETTIP','FAUCET','REACTTIP','FREETIP','RANDTIP','GUILDTIP') NOT NULL DEFAULT 'TIP',
  `date` int(11) NOT NULL,
  `user_server` enum('DISCORD','TELEGRAM') NOT NULL DEFAULT 'DISCORD',
  KEY `token_name` (`token_name`),
  KEY `from_userid` (`from_userid`),
  KEY `to_userid` (`to_userid`),
  KEY `type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;


DROP TABLE IF EXISTS `erc_user`;
CREATE TABLE `erc_user` (
  `token_name` varchar(32) NOT NULL,
  `contract` varchar(128) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `balance_wallet_address` varchar(128) NOT NULL,
  `address_ts` int(11) NOT NULL,
  `real_actual_balance` float NOT NULL DEFAULT 0,
  `token_decimal` tinyint(3) NOT NULL,
  `seed` varchar(512) NOT NULL,
  `create_dump` text NOT NULL,
  `private_key` varchar(512) NOT NULL,
  `public_key` varchar(512) NOT NULL,
  `xprivate_key` varchar(512) NOT NULL,
  `xpublic_key` varchar(512) NOT NULL,
  `user_wallet_address` varchar(128) DEFAULT NULL,
  `lastUpdate` int(11) NOT NULL DEFAULT 0,
  `user_server` enum('DISCORD','TELEGRAM') NOT NULL DEFAULT 'DISCORD',
  `chat_id` bigint(20) DEFAULT NULL,
  KEY `coin_name` (`token_name`),
  KEY `user_id` (`user_id`),
  KEY `user_server` (`user_server`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
