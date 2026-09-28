"""Classifies each LCE-mentioning answer into a theme and scores sentiment with AI Functions."""
import sys
sys.path.insert(0, "../src")
from pyspark.sql import SparkSession
from geologic.config import settings as S
from geologic.datagen.prompts_ext import THEMES

spark = SparkSession.builder.getOrCreate()
labels = ", ".join(f"'{t}'" for t in THEMES)
spark.sql(f"""CREATE OR REPLACE TABLE {S.fq('answer_themes')} AS
SELECT prompt_id, engine, answer,
       ai_classify(answer, ARRAY({labels})) AS theme,
       ai_analyze_sentiment(answer) AS sentiment
FROM {S.fq('v_latest_responses')}
WHERE status = 'ok' AND lce_mentioned""")
print(spark.sql(f"SELECT theme, sentiment, count(*) n FROM {S.fq('answer_themes')} GROUP BY ALL ORDER BY 1, 2").collect())
