from datetime import datetime
from pydantic import BaseModel, field_validator


SAMPLE = [
  {"text": "Invoice", "bbox": [50, 30, 150, 50]},
  {"text": "Date:", "bbox": [50, 100, 90, 120]},
  {"text": "2024-03-21", "bbox": [100, 100, 200, 120]},
  {"text": "Total:", "bbox": [50, 160, 90, 180]},
  {"text": "$1,250.00", "bbox": [100, 160, 200, 180]},
  {"text": "Vendor:", "bbox": [300, 100, 360, 120]},
  {"text": "Acme", "bbox": [370, 100, 410, 120]}
]


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
    

    def parse(self) -> dict[str, str]:
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



class Words(BaseModel):
    lines: list[Line]


    @classmethod
    def from_dict(cls, data: list[dict]) -> "Words":
        words=[Word.from_dict(item) for item in data]

        return cls.from_words(words)
    

    @classmethod
    def from_words(cls, words: list[Word], epsilon: float = 5) -> "Words":
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
    

    def parse(self) -> list[dict[str, str]]:
        return [line.parse() for line in self.lines]
    

    def parse_flat(self) -> dict[str, str]:
        return {k: v for line in self.lines for k, v in line.parse().items()}


class Document(BaseModel):
    date: datetime
    total: float
    vendor: str


    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Document":
        words = Words.from_dict(data)

        # TODO: add support for fuzzy matching
        return cls(**words.parse_flat())
    

    @field_validator("date", mode="before")
    def validate_date(cls, v: str) -> datetime:
        return datetime.strptime(v, "%Y-%m-%d")
    

    @field_validator("total", mode="before")
    def validate_total(cls, v: str) -> float:
        return float(v.replace("$", "").replace(",", ""))
    

    @field_validator("vendor", mode="before")
    def validate_vendor(cls, v: str) -> str:
        return v.strip()


print(Document.from_dict(SAMPLE))
