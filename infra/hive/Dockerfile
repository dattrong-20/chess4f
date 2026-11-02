FROM apache/hive:4.0.0
USER root
RUN mkdir -p /state && chown hive:hive /state \
    && ln -s /opt/hadoop/share/hadoop/tools/lib/hadoop-aws-3.3.6.jar /opt/hive/lib/ \
    && ln -s /opt/hadoop/share/hadoop/tools/lib/aws-java-sdk-bundle-1.12.367.jar /opt/hive/lib/
COPY core-site.xml /opt/hadoop/etc/hadoop/core-site.xml
COPY core-site.xml /opt/hive/conf/core-site.xml
USER hive
