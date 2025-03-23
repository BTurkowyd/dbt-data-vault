import json
import sys
import boto3
from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession

print("Starting Glue ETL job...")

# Get the Aurora credentials from Secrets Manager
args = getResolvedOptions(sys.argv, ['AURORA_CREDS_SECRET', 'DESTINATION_BUCKET'])
client = boto3.client('secretsmanager', region_name='eu-central-1')

try:
    secret = client.get_secret_value(SecretId=args['AURORA_CREDS_SECRET'])
    secrets = json.loads(secret['SecretString'])
    print("Successfully retrieved Aurora credentials.")
    print(secrets)

except Exception as e:
    print(f"ERROR: Failed to retrieve credentials from Secrets Manager: {e}")
    sys.exit(1)

spark = SparkSession.builder \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.warehouse", f"s3://{args['DESTINATION_BUCKET']}/iceberg") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .getOrCreate()

print("Current catalog:", spark.conf.get("spark.sql.defaultCatalog"))

# Construct JDBC URL
jdbc_url = f"jdbc:postgresql://{secrets['host']}:{secrets['port']}/{secrets['dbname']}"

# Fetch the names of the tables in the Aurora database from the public schema, store them in a list.
try:

    table_filter_query = """
            (SELECT table_name
             FROM information_schema.tables
             WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS user_tables
        """


    tables = spark.read \
        .format("jdbc") \
        .option("url", jdbc_url) \
        .option("user", secrets['username']) \
        .option("password", secrets['password']) \
        .option("driver", "org.postgresql.Driver") \
        .option("dbtable", table_filter_query) \
        .load() \
        .select("table_name") \
        .collect()

    table_names = [table['table_name'] for table in tables]
    print("Tables in Aurora:", table_names)
except Exception as e:
    print(f"ERROR: Failed to fetch table names from Aurora: {e}")
    sys.exit(1)

# Load data from Aurora PostgreSQL from all tables
for table_name in table_names:
    try:
        df = spark.read \
            .format("jdbc") \
            .option("url", jdbc_url) \
            .option("dbtable", table_name) \
            .option("user", secrets['username']) \
            .option("password", secrets['password']) \
            .option("driver", "org.postgresql.Driver") \
            .load()

        print(f"Successfully loaded data from {table_name}.")
        df.printSchema()  # Verify the schema

    except Exception as e:
        print(f"ERROR: Failed to load data from {table_name}: {e}")
        sys.exit(1)

    # Register the DataFrame as a temporary SQL view
    df.createOrReplaceTempView(f"tmp_{table_name}")

    # Use Spark SQL to write to Iceberg table in Glue Catalog
    try:
        spark.sql(f"""
        CREATE TABLE IF NOT EXISTS glue_catalog.ecommerce_db_dev.{table_name}
        USING iceberg
        TBLPROPERTIES ('format-version' = '2')
        AS SELECT * FROM tmp_{table_name}
        """)
        print(f"Successfully wrote data to Iceberg table in Glue Catalog for {table_name}.")

    except Exception as e:
        print(f"ERROR: Failed to write Iceberg table to S3 for {table_name}: {e}")
        sys.exit(1)

    del df  # Delete the DataFrame to free up memory

print("Glue ETL job completed.")

# End of script
spark.stop()
