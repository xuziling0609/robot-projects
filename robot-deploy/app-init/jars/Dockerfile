FROM amazoncorretto:21.0.11

ENV TZ=Asia/Shanghai
WORKDIR /home/robot
COPY robot-admin.jar robot-admin.jar
COPY application-cususer.yml application-cususer.yml
ENTRYPOINT ["java", "-Duser.timezone=Asia/Shanghai", "-jar", "robot-admin.jar"]
