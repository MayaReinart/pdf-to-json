from pydantic import BaseModel

import pymupdf


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Word(BaseModel):
    text: str
    bbox: BBox


    @classmethod
    def from_dict(cls, data: dict) -> "Word":
        return Word(text=data["text"], bbox=BBox(x0=data["bbox"][0], y0=data["bbox"][1], x1=data["bbox"][2], y1=data["bbox"][3]))
    
    def text_lower(self) -> str:
        return self.text.strip().lower()


class Line(BaseModel):
    words: list[Word]


    @classmethod
    def from_words(cls, words: list[Word]) -> "Line":
        # Sort by x0 to get the correct order of words in the line
        return cls(words=sorted(words, key=lambda x: x.bbox.x0))
    

    def as_key_value_pairs(self) -> dict[str, str]:
        result = {}

        index = 0

        # Parse the line until the last word is reached
        # TODO: add support for multi-word keys/values
        while index < len(self.words):
            current_word = self.words[index].text_lower()
            next_word = self.words[index + 1].text_lower() if index + 1 < len(self.words) else ""

            if current_word.endswith(":"):
                result[current_word[:-1]] = next_word
                # Next word is already parsed, so we skip it
                index += 1
            
            index += 1

        return result
    

    def __str__(self) -> str:
        return " | ".join([word.text for word in self.words])



class Page(BaseModel):
    lines: list[Line]


    @classmethod
    def from_dict(cls, data: list[dict]) -> "Page":
        words=[Word.from_dict(item) for item in data]

        return cls.from_words(words)
    

    @classmethod
    def from_words(cls, words: list[Word], epsilon: float = 5) -> "Page":
        lines: list[list[Word]] = []

        # Sort by y0 to get the correct order of lines
        for word in sorted(words, key=lambda w: w.bbox.y0):
            placed = False
            for line in lines:
                if abs(line[0].bbox.y0 - word.bbox.y0) < epsilon:
                    line.append(word)
                    placed = True
                    break
            if not placed:
                lines.append([word])

        return cls(lines=[Line.from_words(line) for line in lines])
    

    def __str__(self) -> str:
        return "\n".join([str(line) for line in self.lines])


class Document(BaseModel):
    pages: list[Page]


    @classmethod
    def from_words(cls, words: list[Word]) -> "Document":
        return cls(pages=[Page.from_words(words)])
    

    def __str__(self) -> str:
        return "\nNEW PAGE\n".join([str(page) for page in self.pages])



def main():
    document = pymupdf.open("rpt-scaninvoices.jpg")

    pages: list[Page] = []

    for page in document:
        words: list[Word] = []
        page_text = page.get_textpage_ocr()

        # (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        page_words = page_text.extractWORDS()

        for word in page_words:
            words.append(Word(text=word[4], bbox=BBox(x0=word[0], y0=word[1], x1=word[2], y1=word[3])))

        pages.append(Page.from_words(words))

    document = Document(pages=pages)

    print(document)



if __name__ == "__main__":
    main()
