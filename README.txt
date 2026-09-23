澳门六合彩3分分析

关键修复：
1. 专用3分彩 API 优先：macaumarksix.com/api/macaujc3.com
2. API 数据优先级高于网页解析，避免网页解析覆盖正确特码。
3. 每期第1-6个号码严格保持官网/API开出顺序，不排序。
4. 第7个号码单独作为特码保存。
5. 历史网页/逐期接口用于补齐历史，保留API正确记录。
6. 预测候选号码可排序，但历史开奖号码绝不排序。

Render:
Build: pip install -r requirements.txt
Start: gunicorn app:app
