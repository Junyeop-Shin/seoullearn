package com.seoullearn.mentor.forms;

import com.seoullearn.mentor.common.ApiException;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/forms")
public class FormsController {

    private final FormsService forms;

    public FormsController(FormsService forms) {
        this.forms = forms;
    }

    @GetMapping
    public List<Map<String, String>> list() {
        return forms.list();
    }

    @GetMapping(value = "/{formId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public String get(@PathVariable String formId) {
        return forms.find(formId).orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "해당 양식을 찾을 수 없습니다."));
    }
}
