from pyspark.sql import SparkSession, DataFrame


def get_jdbc_options(jdbc_url: str, secrets: dict) -> dict:
    """
    Construct JDBC options for connecting to PostgreSQL.
    :param jdbc_url: The JDBC URL for the PostgreSQL database.
    :param secrets: The credentials retrieved from AWS Secrets Manager.
    """
    return {
        "url": jdbc_url,
        "user": secrets["username"],
        "password": secrets["password"],
        "driver": "org.postgresql.Driver",
    }


def fetch_table_names(spark: SparkSession, jdbc_options: dict) -> list[str]:
    """
    Fetch the names of all tables in the Aurora PostgreSQL database from the public schema.
    :param spark: The Spark session.
    :param jdbc_options: The JDBC options for connecting to PostgreSQL.
    """
    query = """
        (SELECT table_name
         FROM information_schema.tables
         WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS user_tables
    """
    df = (
        spark.read.format("jdbc")
        .options(**jdbc_options, dbtable=query)
        .load()
        .select("table_name")
    )
    return [row["table_name"] for row in df.collect()]


def load_table_as_df(
    spark: SparkSession, table_name: str, jdbc_options: dict
) -> DataFrame:
    """
    Load a table from PostgreSQL into a Spark DataFrame.
    :param spark: The Spark session.
    :param table_name: The name of the table to load.
    :param jdbc_options: The JDBC options for connecting to PostgreSQL.
    """
    return spark.read.format("jdbc").options(**jdbc_options, dbtable=table_name).load()
