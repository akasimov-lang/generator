"""Conservative Latin Azerbaijani recognition for a detector without an az model."""
import re

# These words and the frequent schwa distinguish az prose from Turkish.
MARKERS=frozenset('və üçün ilə əvvəl qeydiyyat ödəniş məlumat şərtlər oyunçular təhlükəsiz istifadə məbləğ təsdiq seçim haqqında deyil həmçinin hesabın mərc müəyyən etmək üzrə'.split())


def is_azerbaijani(text):
    words=re.findall(r'[^\W\d_]+',text.casefold())
    if len(words)<60:return False
    schwa=sum('ə' in word for word in words)
    markers=[word for word in words if word in MARKERS]
    return schwa>=max(12,len(words)*.08) and len(set(markers))>=4 and len(markers)>=len(words)*.035
