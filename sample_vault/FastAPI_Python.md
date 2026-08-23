# PythonとFastAPIによるWeb開発

## 概要
Pythonを使用した最新のWebバックエンド開発では、型ヒントと非同期処理（async/await）を活用したFastAPIが広く採用されている。
ASGIサーバーであるUvicornと組み合わせて高速に動作する。

## ベクトル検索の実装
NumPyやSciPyを活用することで、外部DBを用いずにローカルメモリ上で数万件のコサイン類似度計算をミリ秒単位で処理可能である。
