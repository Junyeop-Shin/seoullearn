package com.seoullearn.mentor.templates;

import com.seoullearn.mentor.common.ApiException;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.Set;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 종합활동계획서 서식 파일(빈 서식)을 로그인한 멘토에게 내준다. 화면이 받아서 브라우저 안에서 내용을 채운다.
 * 서식 원본은 저장소에 넣지 않고 서버의 폴더(app.templates-dir)에 따로 둔다. 서식에는 멘티·멘토 정보가 없다.
 * 폴더에 파일이 없으면 404: 화면은 내보내지 못한다고 알리고 칸마다 복사해 옮기게 한다.
 */
@RestController
public class TemplatesController {

    private static final String PLAN = "종합활동계획서";
    private static final Set<String> FORMATS = Set.of("docx", "hwpx");

    private final Path dir;

    public TemplatesController(@Value("${app.templates-dir}") String dir) {
        this.dir = Path.of(dir);
    }

    @GetMapping(value = "/api/templates/plan", produces = MediaType.APPLICATION_OCTET_STREAM_VALUE)
    public byte[] plan(@RequestParam String format) {
        if (!FORMATS.contains(format)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "docx 또는 hwpx만 받을 수 있습니다.");
        }
        // 파일 이름은 받은 그대로 둔다: 이름에 '종합활동계획서'가 들어간 그 형식의 파일을 찾는다 (macOS는 한글 파일 이름을 풀어 쓰므로 맞춰서 견준다)
        try (Stream<Path> files = Files.list(dir)) {
            Path found = files.filter(p -> {
                String name = Normalizer.normalize(p.getFileName().toString(), Normalizer.Form.NFC);
                return name.contains(PLAN) && name.endsWith("." + format);
            }).findFirst().orElseThrow(() -> new IOException("없음"));
            return Files.readAllBytes(found);
        } catch (IOException e) {
            throw new ApiException(HttpStatus.NOT_FOUND, "서버에 서식 파일이 없습니다.");
        }
    }
}
