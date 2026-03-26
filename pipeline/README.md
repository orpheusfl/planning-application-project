# ETL pipeline for applications data

### Current sources:

### Transform steps:

### Storage:
- PDF's: S3 Bucket as `<council>/<application-num>/<document-name>.pdf`
- Application Data: RDS
- Document meta-data: RDS

![[static-files/drawSQL-image-export-2026-03-24.jpg]]


## Required environment variables:
For RDS connection:
```
RDS_HOST=
RDS_PORT=
RDS_USER=
RDS_PASSWORD=
RDS_DB_NAME=
```

RDS table names:
```
APPLICATION_FACT_TABLE=
DOCUMENT_FACT_TABLE=

COUNCIL_DIM_TABLE=
STATUS_DIM_TABLE=
APPLICATION_TYPE_DIM_TABLE=
DOCUMENT_TYPE_DIM_TABLE=
```


