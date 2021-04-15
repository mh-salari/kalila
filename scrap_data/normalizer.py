#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 24 2020
@author: MohammadHossein Salari
Source:
      - https://github.com/amnghd/Persian_poems_corpus/blob/master/pers_alphab.py
      - https://github.com/sobhe/hazm/blob/master/hazm/Normalizer.py
      - https://github.com/ICTRC/Parsivar/blob/master/parsivar/normalizer.py
"""
import re


def normalizer(text: str) -> str:
    """
    Summary:


    Arguments:
        text [type:string]

    Returns:
        normalized text [type:string]
    """

    # replacing all spaces,hyphens,... with white space
    space_pattern = (
        r"[\xad\ufeff\u200e\u200d\u200b\x7f\u202a\u2003\xa0\u206e\u200c\x9d]"
    )
    space_pattern = re.compile(space_pattern)
    text = space_pattern.sub(" ", text)

    # remove keshide,
    text = re.sub(r"[ـ\r]", "", text)

    # remove Aarab
    text = re.sub(r"[\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652]", "", text)

    # replace arabic alphabets with equivalent persian alphabet
    regex_list = [
        (r"ء", r"ئ"),
        (r"ﺁ|آ", r"آ"),
        (r"ٲ|ٱ|إ|ﺍ|أ", r"ا"),
        (r"ﺐ|ﺏ|ﺑ", r"ب"),
        (r"ﭖ|ﭗ|ﭙ|ﺒ|ﭘ", r"پ"),
        (r"ﭡ|ٺ|ٹ|ﭞ|ٿ|ټ|ﺕ|ﺗ|ﺖ|ﺘ", r"ت"),
        (r"ﺙ|ﺛ", r"ث"),
        (r"ﺝ|ڃ|ﺠ|ﺟ", r"ج"),
        (r"ڃ|ﭽ|ﭼ", r"چ"),
        (r"ﺢ|ﺤ|څ|ځ|ﺣ", r"ح"),
        (r"ﺥ|ﺦ|ﺨ|ﺧ", r"خ"),
        (r"ڏ|ډ|ﺪ|ﺩ", r"د"),
        (r"ﺫ|ﺬ|ﻧ", r"ذ"),
        (r"ڙ|ڗ|ڒ|ڑ|ڕ|ﺭ|ﺮ", r"ر"),
        (r"ﺰ|ﺯ", r"ز"),
        (r"ﮊ", r"ژ"),
        (r"ݭ|ݜ|ﺱ|ﺲ|ښ|ﺴ|ﺳ", r"س"),
        (r"ﺵ|ﺶ|ﺸ|ﺷ", r"ش"),
        (r"ﺺ|ﺼ|ﺻ", r"ص"),
        (r"ﺽ|ﺾ|ﺿ|ﻀ", r"ض"),
        (r"ﻁ|ﻂ|ﻃ|ﻄ", r"ط"),
        (r"ﻆ|ﻇ|ﻈ", r"ظ"),
        (r"ڠ|ﻉ|ﻊ|ﻋ", r"ع"),
        (r"ﻎ|ۼ|ﻍ|ﻐ|ﻏ", r"غ"),
        (r"ﻒ|ﻑ|ﻔ|ﻓ", r"ف"),
        (r"ﻕ|ڤ|ﻖ|ﻗ", r"ق"),
        (r"ڭ|ﻚ|ﮎ|ﻜ|ﮏ|ګ|ﻛ|ﮑ|ﮐ|ڪ|ك", r"ک"),
        (r"ﮚ|ﮒ|ﮓ|ﮕ|ﮔ", r"گ"),
        (r"ﻝ|ﻞ|ﻠ|ڵ", r"ل"),
        (r"ﻡ|ﻤ|ﻢ|ﻣ", r"م"),
        (r"ڼ|ﻦ|ﻥ|ﻨ", r"ن"),
        (r"ވ|ﯙ|ۈ|ۋ|ﺆ|ۊ|ۇ|ۏ|ۅ|ۉ|ﻭ|ﻮ|ؤ", r"و"),
        (r"ﺔ|ﻬ|ھ|ﻩ|ﻫ|ﻪ|ۀ|ە|ة|ہ", r"ه"),
        (r"ﭛ|ﻯ|ۍ|ﻰ|ﻱ|ﻲ|ں|ﻳ|ﻴ|ﯼ|ې|ﯽ|ﯾ|ﯿ|ێ|ے|ى|ي", r"ی"),
        (r"¬", r"‌"),
        (r"•|·|●|·|・|∙|｡|ⴰ", r"."),
        (r",|٬|٫|‚|，", r"،"),
        (r"ʕ\?", r"؟"),
        (r"ـ|ِ|ُ|َ|ٍ|ٌ|ً|", r""),
    ]

    for pattern, replac in regex_list:
        text = re.sub(pattern, replac, text)

    num_dict = dict()
    num_dict[u"0"] = u"۰"
    num_dict[u"1"] = u"۱"
    num_dict[u"2"] = u"۲"
    num_dict[u"3"] = u"۳"
    num_dict[u"4"] = u"۴"
    num_dict[u"5"] = u"۵"
    num_dict[u"6"] = u"۶"
    num_dict[u"7"] = u"۷"
    num_dict[u"8"] = u"۸"
    num_dict[u"9"] = u"۹"

    num_dict[u"٠"] = u"۰"
    num_dict[u"١"] = u"۱"
    num_dict[u"٢"] = u"۲"
    num_dict[u"٣"] = u"۳"
    num_dict[u"٤"] = u"۴"
    num_dict[u"٥"] = u"۵"
    num_dict[u"٦"] = u"۶"
    num_dict[u"٧"] = u"۷"
    num_dict[u"٨"] = u"۸"
    num_dict[u"٩"] = u"۹"
    num_dict[u"%"] = u"٪"

    # this code replace the keys of num_dict with its values
    num_pattern = re.compile(r"(" + "|".join(num_dict.keys()) + r")")
    text = num_pattern.sub(lambda x: num_dict[x.group()], text)

    punctuation_after, punctuation_before = r"\.:!،؛؟»\]\)\}", r"«\[\(\{"

    regex_list = [
        ('"([^\n"]+)"', r"«\1»"),  # replace quotation with «»
        ('٬([^\n"]+)٬', r"«\1»"),  # replace ٬ with «»
        ('《([^\n"]+)》', r"«\1»"),  # replace Double Angle Bracket with «»
        ("([\d+])\.([\d+])", r"\1٫\2"),  # replace dot with momayez
        (r" ?\.\.\.", " … "),  # replace 3 dots
        (r"([^ ]ه) ی ", r"\1‌ی "),  # fix ی space
        (r"(^| )(ن?می) ", r"\1\2‌"),  # put zwnj after می, نمی
        (
            r"(?<=[^\n\d "
            + punctuation_after
            + punctuation_before
            + "]{2}) (تر(ین?)?|گری?|های?)(?=[ \n"
            + punctuation_after
            + punctuation_before
            + "]|$)",
            r"‌\1",
        ),  # put zwnj before تر, تری, ترین, گر, گری, ها, های
        (
            r"([^ ]ه) (ا(م|یم|ش|ند|ی|ید|ت))(?=[ \n" + punctuation_after + "]|$)",
            r"\1‌\2",
        ),  # join ام, ایم, اش, اند, ای, اید, ات
        ('" ([^\n"]+) "', r'"\1"'),  # remove space before and after quotation
        (" ([" + punctuation_after + "])", r"\1"),  # remove space before
        ("([" + punctuation_before + "]) ", r"\1"),  # remove space after
        (
            "(["
            + punctuation_after[:3]
            + "])([^ "
            + punctuation_after
            + "\d۰۱۲۳۴۵۶۷۸۹])",
            r"\1 \2",
        ),  # put space after . and :
        (
            "([" + punctuation_after[3:] + "])([^ " + punctuation_after + "])",
            r"\1 \2",
        ),  # put space after
        (
            "([^ " + punctuation_before + "])([" + punctuation_before + "])",
            r"\1 \2",
        ),  # put space before
        # Remove repeating characters
        (r"(.)\1+", r"\1\1"),  # keep 2 repeat
    ]

    for pattern, replac in regex_list:
        text = re.sub(pattern, replac, text)

    return text
