from datetime import datetime
from pydantic import BaseModel


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


class Document(BaseModel):
    date: datetime
    total: float
    vendor: str


    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        if "Date" in data:
            date = datetime.strptime(data["Date"], "%Y-%m-%d")
        if "Total" in data:
            total = float(data["Total"].replace("$", "").replace(",", ""))
        if "Vendor" in data:
            vendor = data["Vendor"]
        return cls(date=date, total=total, vendor=vendor)


def parse_lines(data: list[dict]) -> list[list[Word]]:
    words = [Word.from_dict(item) for item in data]

    line_positions = {word.bbox.y0: word for word in words}
    lines = []

    for line_position in line_positions:
        line_words = [word for word in words if word.bbox.y0 == line_position]
        lines.append(line_words)

    

    return lines


def parse_line(line: list[Word]) -> dict[str, str]:
    result = {}

    index = 0

    while index < len(line):
        word = line[index]

        if word.text.endswith(":"):
            result[word.text[:-1]] = line[index + 1].text
            index += 2
        else:
            index += 1

    return result


def parse_document(data: list[dict]) -> Document:
    lines = parse_lines(data)

    parsed_lines = {}
    
    for line in lines:
        parsed_lines.update(parse_line(line))

    return Document.from_dict(parsed_lines)


print(parse_document(SAMPLE))