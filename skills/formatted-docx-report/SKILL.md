---
name: "formatted-docx-report"
description: "Word论文/报告按模板严格排版（字体、字号、固定行距、段后、公式编号）时用：读模板样式逐段设格式并回读校验。"
---

# 按模板严格排版 Word 论文/报告

## 触发

用户给出排版规范（字体、字号、固定行距、段后、公式编号）或参考模板 docx，要求生成/更新论文、报告、说明文档。典型：竞赛论文、项目报告。

## 步骤

1. **解包模板摸清骨架。** 用 zipfile 解压模板，读 `word/styles.xml`（styleId→名称/字体/字号/间距）与 `word/document.xml` 的 `<w:sectPr>`（`w:pgSz` 页面尺寸、`w:pgMar` 页边距）。完成判据：能列出正文/各级标题对应的 styleId 与可用宽度（twips ÷ 20 = pt）。

2. **检查模板残留。** 读 `word/header*.xml`、`word/footer*.xml` 的 `<w:t>` 文本，确认没有上一份文档的标题、题号等字样。完成判据：页眉页脚只剩页码域或为空。

3. **以模板为基底建新文档。** `docx.Document(模板)` 后删除 body 中除 `w:sectPr` 外的全部子元素——这样继承样式表与页面设置，又清空旧正文。完成判据：新文档正文段落数为 0 且 sectPr 仍在。

4. **逐段显式设定格式，不依赖样式继承。** 每个 run 写 `w:rFonts` 的 `w:ascii`/`w:hAnsi`/`w:eastAsia`，字号用 `Pt()`，`bold`/`italic` 显式设置；每段写 `w:spacing`：`w:line="400" w:lineRule="exact"`、`w:afterLines="50" w:beforeLines="0"`；正文段加 `w:ind w:firstLineChars="200"`。完成判据：题目/摘要/标题1/2/3/正文六类元素的字体、字号、粗细、行距、段后逐条核对通过。

5. **公式与编号用制表位。** 公式段加两个制表位：居中位在可用宽度一半、右对齐位在可用宽度处；段文本写作 `"\t公式\t(1)"`，公式 run 用数学字体、编号 run 用西文字体。完成判据：编号贴右边界、公式居中。

6. **表格自己写边框。** 用 `w:tblBorders` 逐边设单线，不要依赖未必存在的 `Table Grid` 样式；表头加粗居中、数据居中，字号可小于正文。完成判据：边框正常显示、列数与表头一致。

7. **回读校验（必做）。** 重新打开输出文件，逐段打印 run 的 `w:rFonts`/字号/粗体与 `w:spacing`，与规范逐条比对；再 `zipfile.ZipFile(输出).testzip()` 验证包完整。完成判据：格式核查全部通过、zip 返回 None。

8. **交付。** 输出到项目根目录并用 `MEDIA:` 行附上路径。

## 要点

- 字号换算：Word 存半磅，13pt→26、15pt→30、17pt→34、19pt→38。
- 「段后 0.5 行」= `w:afterLines="50"`（百分之一行）；「固定行距 20 磅」= `w:line="400" w:lineRule="exact"`（twips）。
- 可用宽度 = (pgSz.w − pgMar.left − pgMar.right) twips ÷ 20 pt。
- 中英混排必须同时设 `w:eastAsia`（中文字体）与 `w:ascii`/`w:hAnsi`（西文字体），否则英文回退到中文字体。
- 标题用「一、」「1.1」这类中文序号时直接写进文本，不依赖 Word 自动编号。
- 论文里的数值必须来自项目实际运行产物（如 outputs/ 下的表与 run summary），不得手写；正文数字要与验证报告一致。
- 环境缺包时 `pip install --break-system-packages python-docx`（PEP668 环境）。
- 用户若要 Word 原生公式对象（OMML）、PDF 或封面目录，属于额外需求，先交付文本公式版本再按需追加。

## 插图（中文标注）

论文/报告常需要结果图。按下列顺序做，可避免「图能出但中文变方框」的返工。

1. **先探工具。** `which matlab octave`；为空则改用 matplotlib 出图，并在回复中明确说明，同时附一份等价的 `.m` 脚本（读 `result*.xlsx` 与诊断 CSV 重画同样的图），不要让用户停在缺工具上。
2. **确认中文字体。** matplotlib 默认只有 DejaVu/STIX，中文会渲染成方框。`apt-get install -y fonts-noto-cjk` 后，删除缓存并强制重扫：`rm -rf ~/.cache/matplotlib`，再 `matplotlib.font_manager._load_fontmanager(try_read_cache=False)`；把 matplotlib 实际注册的族名（可能是 `Noto Sans CJK JP`，.ttc 内含简体字形）放进 `font.sans-serif` 首位，并设 `axes.unicode_minus=False`。
3. **完成判据：零缺字告警。** 出图包在 `warnings.catch_warnings(record=True)` 里，确认没有 `missing from font` / `Glyph` 告警后才交付。注意 `fc-list` 在无 fontconfig 缓存的机器上可能返回 0，**不能**用它判断字体可用性，以 matplotlib 的字体列表为准。
4. **嵌入 docx。** 图段居中、`add_picture(width=Cm(可用宽度))`（A4+2.5 cm 边距约 15 cm），图题用「图表标题」样式（10.5pt 加粗居中）放在图下方；图题文本与正文引用编号一致。
