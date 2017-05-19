// MAGIC %md ![Wikipedia/Spark Logo](http://curriculum-release.s3-website-us-west-2.amazonaws.com/wiki-book/general/wiki_spark.png)  
// MAGIC 
// MAGIC #### Analyze hourly web traffic to Wikimedia projects
// MAGIC 
// MAGIC **Objective:**
// MAGIC Study traffic patterns to all English Wikimedia projects from the past hour
// MAGIC 
// MAGIC **Time to Complete:**
// MAGIC 30 mins
// MAGIC 
// MAGIC **Data Source:**
// MAGIC Last hour's English Projects Pagecounts (~35 MB compressed parquet file)
// MAGIC 
// MAGIC **Business Questions:**
// MAGIC 
// MAGIC * Question # 1) How many different English Wikimedia projects saw traffic in the past hour?
// MAGIC * Question # 2) How much traffic did each English Wikimedia project get in the past hour?
// MAGIC * Question # 3) What were the 25 most popular English articles in the past hour?
// MAGIC * Question # 4) How many requests did the "Apache Spark" article recieve during this hour?
// MAGIC * Question # 5) Which Apache project received the most requests during this hour?
// MAGIC * Question # 6) What percentage of the 5.1 million English articles were requested in the past hour?
// MAGIC * Question # 7) How many total requests were there to English Wikipedia Desktop edition in the past hour?
// MAGIC * Question # 8) How many total requests were there to English Wikipedia Mobile edition in the past hour?
// MAGIC 
// MAGIC **Technical Accomplishments:**
// MAGIC - Create a DataFrame
// MAGIC - Print the schema of a DataFrame
// MAGIC - Use the following Transformations: `select()`, `distinct()`, `groupBy()`, `sum()`, `orderBy()`, `filter()`, `limit()`
// MAGIC - Use the following Actions: `show()`, `count()`
// MAGIC - Learn about Wikipedia Namespaces

// COMMAND ----------

// MAGIC %md ####![Wikipedia Logo Tiny](http://curriculum-release.s3-website-us-west-2.amazonaws.com/wiki-book/general/logo_wikipedia_tiny.png) **Introduction: Wikipedia Pagecounts**
