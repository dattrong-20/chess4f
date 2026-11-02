FROM apache/spark:3.5.0-scala2.12-java11-python3-ubuntu
USER root
# Fixed Maven coordinates. No credentials are baked into the image.
RUN python3 - <<'PY'
import urllib.request
from pathlib import Path
base = 'https://repo.maven.apache.org/maven2/'
artifacts = [
 'io/delta/delta-spark_2.12/3.0.0/delta-spark_2.12-3.0.0.jar',
 'io/delta/delta-storage/3.0.0/delta-storage-3.0.0.jar',
 'org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar',
 'com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar',
]
for artifact in artifacts:
    urllib.request.urlretrieve(base + artifact, Path('/opt/spark/jars') / artifact.rsplit('/', 1)[1])
PY
USER 185
