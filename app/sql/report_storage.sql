CREATE TABLE dbo.report_definitions (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    schema_name NVARCHAR(128) NOT NULL,
    table_name NVARCHAR(128) NOT NULL,
    selected_fields NVARCHAR(MAX) NOT NULL,
    filters NVARCHAR(MAX) NOT NULL,
    computed_fields NVARCHAR(MAX) NOT NULL,
    sort NVARCHAR(MAX) NULL,
    row_limit INT NULL,
    tags NVARCHAR(200) NULL,
    created_by NVARCHAR(128) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    is_deleted BIT NOT NULL DEFAULT 0
);
GO
CREATE INDEX IX_report_definitions_active ON dbo.report_definitions(is_deleted, updated_at DESC);
GO

CREATE TABLE dbo.report_runs (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    report_id UNIQUEIDENTIFIER NOT NULL,
    run_started_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    run_finished_at DATETIME2 NULL,
    status NVARCHAR(30) NOT NULL,
    row_count INT NULL,
    error_message NVARCHAR(MAX) NULL
);
GO
CREATE INDEX IX_report_runs_reportid_time ON dbo.report_runs(report_id, run_started_at DESC); 