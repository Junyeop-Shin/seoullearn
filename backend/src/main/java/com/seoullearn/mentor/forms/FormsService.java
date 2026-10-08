package com.seoullearn.mentor.forms;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

/** forms/*.json 양식 스키마를 읽는다. 양식 하나 = 파일 하나라서 파일을 추가하면 바로 목록에 나온다. */
@Service
public class FormsService {

    private static final Pattern FORM_ID = Pattern.compile("^[a-z0-9_]{1,50}$");

    private final Path dir;
    private final ObjectMapper mapper;

    public FormsService(@Value("${app.forms-dir}") String dir, ObjectMapper mapper) {
        this.dir = Path.of(dir);
        this.mapper = mapper;
    }

    public List<Map<String, String>> list() {
        try (Stream<Path> files = Files.list(dir)) {
            return files.filter(p -> p.getFileName().toString().endsWith(".json")).sorted()
                    .map(this::summary).toList();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** 양식 JSON 원문. 없는 양식이거나 형식에 맞지 않는 이름이면 빈 값. */
    public Optional<String> find(String formId) {
        if (!FORM_ID.matcher(formId).matches()) {
            return Optional.empty(); // 경로 조작 방지
        }
        Path file = dir.resolve(formId + ".json");
        if (!Files.isRegularFile(file)) {
            return Optional.empty();
        }
        try {
            return Optional.of(Files.readString(file, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private Map<String, String> summary(Path file) {
        try {
            JsonNode node = mapper.readTree(Files.readString(file, StandardCharsets.UTF_8));
            String name = file.getFileName().toString();
            return Map.of(
                    "form_id", node.path("form_id").asString(name.substring(0, name.length() - ".json".length())),
                    "title", node.path("title").asString(""),
                    "version", node.path("version").asString(""));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
