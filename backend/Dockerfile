FROM gradle:9-jdk21 AS build
WORKDIR /app
COPY settings.gradle build.gradle ./
COPY src ./src
# 테스트는 이미지 밖에서 ./gradlew test 로 돌린다
RUN gradle bootJar -x test --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --system --no-create-home app
COPY --from=build /app/build/libs/*.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
