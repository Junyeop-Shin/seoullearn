package com.seoullearn.mentor.unanswered;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UnansweredQuestionRepository extends JpaRepository<UnansweredQuestion, Long> {

    List<UnansweredQuestion> findTop1000ByOrderByCreatedOnDescIdDesc();
}
