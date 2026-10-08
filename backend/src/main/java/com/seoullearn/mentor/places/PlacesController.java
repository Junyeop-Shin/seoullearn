package com.seoullearn.mentor.places;

import com.seoullearn.mentor.common.ApiException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 협약 장소 지도용 자료. 장소 목록 파일을 그대로 내주고, 카카오맵 JavaScript 키를 화면에 알려 준다.
 * 장소 정보에는 멘티·멘토 정보가 없다. 키는 브라우저에 노출되는 공개 키이며 카카오에 등록한 주소에서만 동작한다.
 */
@RestController
public class PlacesController {

    private final Path placesFile;
    private final String kakaoMapJsKey;

    public PlacesController(@Value("${app.places-file}") String placesFile, @Value("${app.kakao-map-js-key:}") String kakaoMapJsKey) {
        this.placesFile = Path.of(placesFile);
        this.kakaoMapJsKey = kakaoMapJsKey.trim();
    }

    @GetMapping(value = "/api/places", produces = MediaType.APPLICATION_JSON_VALUE)
    public String places() {
        try {
            return Files.readString(placesFile, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new ApiException(HttpStatus.NOT_FOUND, "장소 목록을 찾을 수 없습니다.");
        }
    }

    /** 화면이 쓰는 공개 설정. 비밀값은 넣지 않는다. */
    @GetMapping("/api/config")
    public Map<String, String> config() {
        return Map.of("kakaoMapJsKey", kakaoMapJsKey);
    }
}
