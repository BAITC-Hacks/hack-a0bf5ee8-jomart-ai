#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAQ-бот для репетиции хакатона.
Отвечает на 5 вопросов по темам: время, команда, трек, сдача, призы.
"""

import os
import re
import sys
from difflib import SequenceMatcher

# Настройка UTF-8 для корректного вывода в терминале Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

# Ключевые корни/слова по 5 темам
TOPIC_KEYWORDS = {
    "time": [
        "врем", "длит", "длительн", "скольк", "когда", "во сколько", "расписан",
        "тайминг", "минут", "час", "начал", "таймер", "срок"
    ],
    "team": [
        "команд", "состав", "участник", "участ", "человек", "люд", "капитан",
        "jomart", "соло", "групп", "кто"
    ],
    "track": [
        "трек", "тем", "направлен", "задач", "кейс", "проект", "разработк",
        "ai", "бот", "ассистент"
    ],
    "submission": [
        "сдач", "сдат", "сдать", "отправ", "загруз", "куда", "дедлайн",
        "ссылк", "github", "репозитор", "гитхаб", "readme"
    ],
    "prizes": [
        "приз", "наград", "победител", "мерч", "диплом", "подарок", "бонус",
        "выигрыш", "балл", "деньг", "вознагражд"
    ],
}

STOP_WORDS = {
    "в", "во", "и", "на", "с", "со", "к", "ко", "по", "о", "об", "обо",
    "у", "из", "за", "до", "от", "для", "а", "но", "как", "какой", "какая",
    "какие", "какое", "что", "это", "ли", "же", "бы", "то", "или", "не"
}

FALLBACK_MESSAGE = "Не знаю. Попробуйте спросить о времени, команде, треке, сдаче или призах."


class FAQBot:
    def __init__(self, faq_path="faq.txt"):
        self.faq_path = faq_path
        self.faq_items = []
        self.load_faq()

    def load_faq(self):
        """Загружает пары вопрос-ответ из faq.txt."""
        if not os.path.exists(self.faq_path):
            # Попробуем найти рядом со скриптом
            base_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(base_dir, self.faq_path)
            if os.path.exists(alt_path):
                self.faq_path = alt_path
            else:
                raise FileNotFoundError(f"Файл {self.faq_path} не найден!")

        with open(self.faq_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Разделяем блоки по пустым строкам
        blocks = re.split(r"\n\s*\n", content)
        self.faq_items = []

        topics_order = ["time", "team", "track", "submission", "prizes"]

        for idx, block in enumerate(blocks):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            q_line = ""
            a_line = ""
            for line in lines:
                if line.startswith(("В:", "Q:", "вопрос:", "Вопрос:")):
                    q_line = re.sub(r"^(?:В|Q|вопрос|Вопрос)\s*:\s*", "", line, flags=re.IGNORECASE)
                elif line.startswith(("О:", "A:", "ответ:", "Ответ:")):
                    a_line = re.sub(r"^(?:О|A|ответ|Ответ)\s*:\s*", "", line, flags=re.IGNORECASE)

            if q_line and a_line:
                topic = topics_order[idx] if idx < len(topics_order) else "general"
                self.faq_items.append({
                    "id": idx,
                    "topic": topic,
                    "question": q_line,
                    "answer": a_line,
                    "keywords": TOPIC_KEYWORDS.get(topic, [])
                })

    @staticmethod
    def _normalize(text: str) -> str:
        """Приводит текст к нижнему регистру и удаляет знаки препинания."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
        return " ".join(text.split())

    def _calc_score(self, query: str, item: dict) -> float:
        """
        Вычисляет степень совпадения вопроса пользователя с элементом FAQ.
        Требует наличия смысловых совпадений (ключевые слова или общие корни).
        """
        norm_query = self._normalize(query)
        raw_words = norm_query.split()
        if not raw_words:
            return 0.0

        # Фильтруем стоп-слова
        words = [w for w in raw_words if w not in STOP_WORDS]
        if not words:
            # Если запрос состоял только из стоп-слов (напр. "что это?")
            words = raw_words

        # 1. Поиск совпадений по ключевым корням темы
        matched_keywords = 0
        for kw in item["keywords"]:
            for word in words:
                if word.startswith(kw) or (len(kw) >= 4 and kw in word):
                    matched_keywords += 1
                    break

        # 2. Пересечение значимых слов запроса со словами эталонного вопроса
        norm_q = self._normalize(item["question"])
        q_words = [qw for qw in norm_q.split() if qw not in STOP_WORDS and len(qw) >= 4]

        matched_content_words = 0
        for w in words:
            if len(w) < 4:
                continue
            w_stem = w[:4]
            if any(qw.startswith(w_stem) or qw[:4] == w_stem for qw in q_words):
                matched_content_words += 1

        # Если нет ни одного тематического ключевого слова и ни одного совпадения по смыслу
        if matched_keywords == 0 and matched_content_words == 0:
            return 0.0

        # 3. Схожесть строки (difflib) как дополнительный вес
        ratio = SequenceMatcher(None, norm_query, norm_q).ratio()

        score = (matched_keywords * 3.0) + (matched_content_words * 2.0) + (ratio * 1.5)
        return score

    def answer(self, query: str) -> str:
        """Находит наиболее подходящий ответ на запрос пользователя."""
        if not query or not query.strip():
            return FALLBACK_MESSAGE

        best_score = 0.0
        best_item = None

        for item in self.faq_items:
            score = self._calc_score(query, item)
            if score > best_score:
                best_score = score
                best_item = item

        # Порог совпадения: минимум 1 попадание по ключевому слову или достаточная схожесть
        if best_item and best_score >= 1.5:
            return best_item["answer"]

        return FALLBACK_MESSAGE


def run_tests():
    """Автоматическая проверка точности ответов на типовых запросах."""
    print("=" * 60)
    print("Запуск автоматических тестов FAQ-бота...")
    print("=" * 60)

    bot = FAQBot()
    test_cases = [
        ("Сколько длится репетиция?", "время"),
        ("Во сколько начало?", "время"),
        ("Какой тайминг мероприятия?", "время"),
        ("Сколько участников в команде?", "команда"),
        ("Кто входит в команду?", "команда"),
        ("Какой у нас трек?", "трек"),
        ("Какая тема хакатона?", "трек"),
        ("Куда кидать ссылку на гитхаб?", "сдача"),
        ("Как сдать готовый проект?", "сдача"),
        ("Что получат победители?", "призы"),
        ("Какие призы за первое место?", "призы"),
        ("Какая погода сегодня в Париже?", "fallback"),
        ("Расскажи анекдот", "fallback"),
    ]

    all_passed = True
    for query, expected_category in test_cases:
        ans = bot.answer(query)
        if expected_category == "fallback":
            ok = ans == FALLBACK_MESSAGE
        elif expected_category == "время":
            ok = "30" in ans or "60" in ans
        elif expected_category == "команда":
            ok = "Jomart Ai" in ans or "участник" in ans
        elif expected_category == "трек":
            ok = "трек" in ans or "AI-помощников" in ans
        elif expected_category == "сдача":
            ok = "GitHub" in ans or "README.md" in ans
        elif expected_category == "призы":
            ok = "мерч" in ans or "диплом" in ans or "приз" in ans
        else:
            ok = False

        status = "✅ PASS" if ok else "❌ FAIL"
        if not ok:
            all_passed = False
        print(f"[{status}] Вопрос: \"{query}\"")
        print(f"         Ответ:  \"{ans}\"")

    print("-" * 60)
    if all_passed:
        print("Все тесты успешно пройдены! 🚀")
    else:
        print("Некоторые тесты не прошли.")
    return all_passed


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--test", "-t", "test"):
            success = run_tests()
            sys.exit(0 if success else 1)
        else:
            # Ответ на единичный аргумент-вопрос
            bot = FAQBot()
            query = " ".join(sys.argv[1:])
            print(bot.answer(query))
            return

    # Интерактивный режим чата в терминале
    print("=" * 60)
    print("🤖 FAQ-бот репетиции запущен!")
    print("Вы можете задавать вопросы о времени, команде, треке, сдаче или призах.")
    print("Для выхода введите 'выход', 'exit' или 'quit'.")
    print("=" * 60)

    try:
        bot = FAQBot()
    except Exception as e:
        print(f"Ошибка загрузки базы FAQ: {e}")
        return

    while True:
        try:
            user_input = input("\nВы: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nДо свидания!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "выход", "выйти", "q", ":q"):
            print("Бот: До свидания и удачи на хакатоне!")
            break

        ans = bot.answer(user_input)
        print(f"Бот: {ans}")


if __name__ == "__main__":
    main()
