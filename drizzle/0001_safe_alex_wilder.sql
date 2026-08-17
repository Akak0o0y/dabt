CREATE TABLE `auditEvidenceSnapshots` (
	`id` varchar(64) NOT NULL,
	`userId` int NOT NULL,
	`sourceDocumentHash` varchar(64) NOT NULL,
	`integrityHash` varchar(64) NOT NULL,
	`decision` varchar(32) NOT NULL,
	`decisionRuleId` varchar(191),
	`classification` varchar(32) NOT NULL,
	`policyMapVersion` varchar(64) NOT NULL,
	`classificationEvidenceJson` text NOT NULL,
	`auditJson` text NOT NULL,
	`legalReviewDisclaimerEn` text NOT NULL,
	`legalReviewDisclaimerAr` text NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `auditEvidenceSnapshots_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `auditEvidenceSnapshots` ADD CONSTRAINT `auditEvidenceSnapshots_userId_users_id_fk` FOREIGN KEY (`userId`) REFERENCES `users`(`id`) ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `auditEvidenceSnapshots_user_created_idx` ON `auditEvidenceSnapshots` (`userId`,`createdAt`);