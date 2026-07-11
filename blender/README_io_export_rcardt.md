# RCARDT Model Exporter（Blender 4.2+ アドオン）

`sample_RCARDT.zip` 内の `00000000` ファイル（PS1レースゲーム「C1 Circuit」系の
車体モデルフォーマット、`c1circuit_rcardt_model.bt` で定義）を生成するBlenderアドオンです。

## 検証について
`c1circuit_rcardt_model.bt` を基にPythonでpack/unpackロジックを実装し、
同梱サンプル5ファイル全てで **バイト単位の完全一致（ラウンドトリップ検証）** を確認済みです
（唯一の相違はランタイム専用ポインタ `ptr_mdl` と、SW20サンプル末尾の無関係なゼロ埋め60バイトのみ）。
つまりファイルの構造・ビットフィールドの解釈は正確です。

## インストール
1. `io_export_rcardt.zip` をそのまま Blender の
   `Edit > Preferences > Add-ons > Install...` からインストールし、有効化してください。
2. `File > Export > RCARDT Model (00000000)` からエクスポートできます。

## 使い方
### 1. オブジェクト側の設定（RCARDT Node Editor）
出力ファイルは **常に4つの固定ノード**（例: 車体本体＋パーツ×3、実データでは
おそらく本体＋ホイール関連）から構成されます。
- 対象にしたいメッシュオブジェクトを選択 → プロパティパネルの
  **オブジェクトタブ** に **「RCARDT Node Editor」** パネルが表示されます。
- `Include in RCARDT Export` を有効化
- `Node Index` (0-3) でどのノード枠に割り当てるか指定
- `Auto From Object Transform` を有効にすると、そのオブジェクトの
  Location/Rotation からノードヘッダーの position/rotation を自動計算します
  （無効にすると手動で整数値を入力できます）

### 2. マテリアル側の設定（RCARDT Material Editor）
- マテリアルを選択 → プロパティパネルの **マテリアルタブ** に
  **「RCARDT Material Editor」** パネルが表示されます。
- Flat Color（サーフェス単位の単色。フォーマット上、頂点カラーではなく面単位で1色のみ保持）
- GPU Command Flags（Textured / Raw Texture / Semi Transparent / Gouraud）
- CLUT（パレット位置）、Texture Page（テクスチャページ位置・半透明モード・色深度）
- Advanced / Unknown Fields（末尾の未解明6ショート値なども手動調整可能）

### 3. エクスポート時のオプション
`File > Export > RCARDT Model` のサイドパネルで以下を調整できます。
- **Selected Objects Only**: 選択中オブジェクトのみを対象にする
- **Position Scale**: Blender座標→ゲーム内整数座標への倍率（デフォルト100 = 1m/100units想定）
- 軸変換は常時有効の固定処理になりました（下記参照）。トグルは廃止しています。
- **Reorder Quad Vertices (Fan → Strip)**: Blenderの面頂点順（ファン順）をPS1 GPUの
  三角ストリップ順（0,1,3,2）に並べ替え（四角形をどちらの対角線で分割するかのみに影響し、表裏には影響しません）
- **Flip Winding (Front/Back Facing)**: 全ての三角形の頂点順（ワインディング）を反転し、
  ゲーム内での表裏判定を逆転させます。**エクスポート後にゲーム内で全ての面が裏返って
  見える（カリングされる）場合はこれを有効にしてください。**
  内部的には各サーフェスの頂点順の2番目・3番目を入れ替えるだけの単純な処理なので、
  四角形の分割対角線（トポロジー）自体は変えず、表裏だけを反転します。
- **Flip UV V**: V座標を反転（VRAMの上下基準に合わせる）
- **Auto-Triangulate N-gons**: 5角形以上の面を自動的に三角形分割（本フォーマットは三角形と四角形のみ対応）

## 軸変換について（常時有効・固定）
実機での動作確認により、**エクスポート時に頂点座標・Node位置の両方へX軸+90度回転を
常に適用する**仕様に固定しました（オプションではなくなりました）。これによりBlender上の
モデルの向きとゲーム内での向きが一致することを確認済みです。

## 未確定・要検証のパラメータ（ゲーム内での確認を推奨）
バイナリのフィールド意味は完全一致を確認済みですが、以下の項目は
**エクスポート時にBlender側でどう解釈するか**という「変換の向き」の部分であり、
実機/エミュレータでの見た目確認をおすすめします。UIから調整可能にしてあります。
- 座標スケール（Position Scale）
- 四角ポリゴンの頂点順（ファン→ストリップ変換）
- Node position/rotation の単位・回転角度換算（現状12bit角度 0-4095 = 0-360度と仮定）

## ファイル構成
```
io_export_rcardt/
├── __init__.py          # アドオン登録
├── rcardt_format.py      # バイナリ構造体のpack実装（.btと1対1対応）
├── rcardt_props.py        # オブジェクト/マテリアルのプロパティ定義
├── rcardt_editor.py        # 「RCARDT Node Editor」「RCARDT Material Editor」UI
└── export_rcardt.py        # エクスポート処理本体・オペレーター
```
