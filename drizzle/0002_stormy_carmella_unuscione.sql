CREATE TABLE `auditEvidenceReviews` (
	`id` varchar(64) NOT NULL,
	`evidenceSnapshotId` varchar(64) NOT NULL,
	`evidenceIntegrityHash` varchar(64) NOT NULL,
	`reviewerUserId` int NOT NULL,
	`disposition` enum('approved','rejected') NOT NULL,
	`rationaleEn` text NOT NULL,
	`rationaleAr` text NOT NULL,
	`integrityHash` varchar(64) NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `auditEvidenceReviews_id` PRIMARY KEY(`id`),
	CONSTRAINT `auditEvidenceReviews_snapshot_unique` UNIQUE(`evidenceSnapshotId`)
);
--> statement-breakpoint
ALTER TABLE `auditEvidenceReviews` ADD CONSTRAINT `review_snapshot_fk` FOREIGN KEY (`evidenceSnapshotId`) REFERENCES `auditEvidenceSnapshots`(`id`) ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `auditEvidenceReviews` ADD CONSTRAINT `review_reviewer_fk` FOREIGN KEY (`reviewerUserId`) REFERENCES `users`(`id`) ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `auditEvidenceReviews_reviewer_created_idx` ON `auditEvidenceReviews` (`reviewerUserId`,`createdAt`);
