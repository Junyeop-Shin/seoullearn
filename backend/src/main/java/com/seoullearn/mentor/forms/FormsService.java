package com.seoullearn.mentor.forms;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/** forms/*.json 양식 스키마를 읽는다. 양식 하나 = 파일 하나다. */
@Service
public class FormsService {

    private static final Pattern FORM_ID = Pattern.compile("^[a-z0-9_]{1,50}$");

    private final Path dir;

    public FormsService(@Value("${app.forms-dir}") String dir) {
        this.dir = Path.of(dir);
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
}
