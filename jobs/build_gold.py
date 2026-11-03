"""One bounded Spark driver; real Delta/S3 I/O, not a distributed cluster claim."""
import os
import re

from pyspark.sql import SparkSession

release = os.environ.get("CHESS4F_RELEASE", "")
if not re.fullmatch(r"r_[0-9a-f]{32}", release):
    raise ValueError("CHESS4F_RELEASE must be an exported release ID")
base = f"s3a://chess4f/releases/{release}"
spark = (SparkSession.builder.appName(f"chess4f-{release}")
         .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
         .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.sql.session.timeZone", "UTC")
         .config("spark.databricks.delta.snapshotPartitions", "2")
         .config("spark.hadoop.fs.s3a.endpoint", "http://object-store:9000")
         .config("spark.hadoop.fs.s3a.path.style.access", "true")
         .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
         .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.EnvironmentVariableCredentialsProvider")
         .config("spark.delta.logStore.class", "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore")
         .getOrCreate())
spark.sparkContext.setLogLevel("WARN")
try:
    games = spark.read.format("delta").load(f"{base}/silver/games")
    games.createOrReplaceTempView("games")
    openings = spark.sql("""
      SELECT source, year_month, speed, rating_group, opening_family,
        count(*) n_games,
        sum(CASE WHEN result='1-0' THEN 1 ELSE 0 END) white_wins,
        sum(CASE WHEN result='1/2-1/2' THEN 1 ELSE 0 END) draws,
        sum(CASE WHEN result='0-1' THEN 1 ELSE 0 END) black_wins,
        sum(white_score) white_score_sum
      FROM games WHERE rated AND opening_family IS NOT NULL
      GROUP BY source, year_month, speed, rating_group, opening_family
    """)
    players = spark.sql("""
      SELECT source, white player, black opponent, game_key, played_at, year_month, speed,
        'white' color, opening_family,
        CASE white_score WHEN 1 THEN 'win' WHEN 0 THEN 'loss' ELSE 'draw' END outcome,
        white_elo rating, black_elo opponent_rating, white_score score FROM games
      UNION ALL
      SELECT source, black, white, game_key, played_at, year_month, speed,
        'black', opening_family,
        CASE white_score WHEN 0 THEN 'win' WHEN 1 THEN 'loss' ELSE 'draw' END,
        black_elo, white_elo, 1-white_score FROM games
    """)
    for name, actual in [("openings", openings), ("player_games", players)]:
        expected = spark.read.format("delta").load(f"{base}/gold/{name}")
        actual = actual.select(expected.columns)
        # Full multiset equality, not merely comparing total counts.
        if actual.exceptAll(expected).limit(1).count() or expected.exceptAll(actual).limit(1).count():
            raise RuntimeError(f"Spark/local parity failed: {name}")
        # Release paths are immutable: retry must allocate a new release.
        actual.coalesce(2).write.format("delta").mode("errorifexists").save(f"{base}/spark/gold/{name}")
        print(f"CHESS4F_PARITY_OK {name} rows={actual.count()}", flush=True)
    print(f"CHESS4F_SPARK_COMPLETE {release}", flush=True)
finally:
    spark.stop()
