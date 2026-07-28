# RCARDT Model Import / Export（Blender 4.2+ アドオン）

PS1レースゲーム「C1 Circuit」の車体モデル `RCARDT/*/00000000` を
Blenderで読み書きするアドオンです。

## 検証について
市販版ディスクの **全15車種**について、`インポート → エクスポート` が
**バイト単位で完全一致**することを Blender 4.3.2 上で確認済みです
（既定オプションのまま。`ptr_mdl`・SW20末尾の60バイトパディングを含む）。

仕様の詳細は [RCARDT_format_doc.md](../doc/RCARDT_format_doc.md) を参照。

## インストール
1. `io_export_rcardt` フォルダをzip化し、Blender の
   `Edit > Preferences > Add-ons > Install...` からインストールして有効化
2. `File > Import > RCARDT Model (00000000)` でインポート
3. `File > Export > RCARDT Model (00000000)` でエクスポート

---

## 標準的な作業手順

```
C1CircuitTool rcardt-unpack -i NA8C.S -o work/NA8C
   work/NA8C/00000000.BIN        モデル
   work/NA8C/000_body_256x64.TIM テクスチャ（ps-imageで編集）
   work/NA8C/clut_presets.json   CLUTスロット定義

Blender で work/NA8C/00000000.BIN をインポート
   → 同フォルダの clut_presets.json が自動で読み込まれる
   → モデルを編集し、同じフォルダに 00000000.BIN としてエクスポート

C1CircuitTool rcardt-pack -i work/NA8C -o out
   → out/NA8C.S
```

---

## 1. CLUTスロット（パレット位置の一元管理）

パレットのVRAM位置は、モデル側とテクスチャ側で**同じ場所を違う数値で**
指定する必要があります（モデル側は X ÷ 16）。これを人手で合わせると必ず
食い違うため、**スロット名を選ぶだけ**で両方に正しい値が入るようにしています。

- **Scene プロパティ → 「RCARDT CLUT Slots」** で、参照する
  `clut_presets.json` を確認・変更できます
  （モデルをインポートすると自動で設定されます）
- **Material プロパティ → 「RCARDT Material Editor」→ CLUT** の
  `CLUT Slot` でスロットを選択します
- 選択すると、モデル側・テクスチャ側それぞれに書かれる値がその場に表示されます
- `Manual (raw X/Y)` を選ぶと従来どおり生の値を直接入力できます

`clut_presets.json` が無い場合は組み込みスロット
（`body` = 496 / `shadow` = 503 / `tire` = 504、いずれも VRAM X = 128）が使われます。

---

## 2. インポート

`File > Import > RCARDT Model (00000000)`

- 4つのノードをそれぞれ独立したメッシュオブジェクトとして作成し、
  `Node Index`・ノード位置/回転・`ptr_mdl` を保持します
- **マテリアルは内容が同じものを1つにまとめます。** GPU ステート
  （色・コマンドフラグ・CLUT・TexPage）が一致する面は同じマテリアルを共有し、
  4つのノードをまたいで共通化されます
  （例: FD3S は 242面 → **4マテリアル**）
- CLUT座標が `clut_presets.json` のスロットと一致するマテリアルには、
  そのスロット名が自動で割り当てられます

### オプション
| オプション | 説明 |
|---|---|
| Position Scale | ファイルの整数座標を割る値。エクスポート時と同じ値にすること |
| Reorder Quad Vertices / Flip Winding / Flip UV V | エクスポート側の同名オプションの逆変換。既定のまま揃えれば一致します |
| Use CLUT Slots | 同フォルダの `clut_presets.json` を読み込み、スロット名を割り当てる |
| Merge Vertices By Distance | 重複頂点を結合して編集しやすいメッシュにする（既定OFF＝1面1クアッドのまま） |
| Skip Empty Nodes | 面を持たないノードのオブジェクトを作らない |

### インポート時の警告
- **三角形面が含まれる場合** — ゲームは四角形しか正しく描画しません
- **法線がジオメトリと一致しない場合** — エクスポート時に再計算されるため、
  そのファイルはバイト一致で書き戻せません（メニュー用モデルから変換された
  データで発生します）

---

## 3. マテリアル設定（RCARDT Material Editor）

- **Flat Color** — 面単位の単色（頂点カラーではありません）
- **GPU Command Flags** — Textured / Raw Texture / Semi Transparent / Gouraud
- **CLUT** — 上記のスロット選択
- **Texture Page** — テクスチャページ位置・半透明モード・色深度・Texture Disable
- **Advanced** — Render Type、TexPageの未解明ビット

> **面法線について**
> サーフェス末尾12バイトは `Unknown Tail (0x2C)` として手入力可能でしたが、
> 実体は**面法線**（`cross(v1-v0, v2-v0)` の int32×3）であることが
> 市販版15車種・全3,341面で確認されました。ジオメトリから一意に決まる
> 派生値のため、**エクスポート時に自動計算**する方式に変更し、
> マテリアルの項目は廃止しています。
> なお描画順（Zソート）とは無関係です。

---

## 4. オブジェクト設定（RCARDT Node Editor）

出力ファイルは **常に4つの固定ノード**で構成されます。ゲームが
「0番=ボディ、1/2番=前輪、3番=後輪」を前提に描画するため、
**増減も入れ替えもできません。**

- `Include in RCARDT Export` を有効化
- `Node Index` (0-3) を指定
- `Auto From Object Transform` でオブジェクトの Location/Rotation から
  ノードヘッダーを自動計算（無効にすると手動で整数値を入力）

---

## 5. エクスポート時のオプション

`File > Export > RCARDT Model` のサイドパネルで調整できます。
ファイル名は **`00000000.BIN` が既定**になります（パック時にこの名前が必要）。

- **Selected Objects Only**: 選択中オブジェクトのみを対象にする
- **Position Scale**: Blender座標→ゲーム内整数座標への倍率（既定100 = 1m/100units想定）
- **Reorder Quad Vertices (Fan → Strip)**: Blenderの面頂点順をPS1の
  三角ストリップ順 `(0,1,3,2)` に並べ替え（四角形の分割対角線のみに影響、表裏は不変）
- **Flip Winding (Front/Back Facing)**: 全三角形のワインディングを反転。
  **ゲーム内で全面が裏返って見える場合はこれを有効に**（既定ON）
- **Flip UV V**: V座標を反転（VRAMの上下基準に合わせる、既定ON）
- **Auto-Triangulate N-gons**: 5角形以上の面を自動分割
  （※ゲームは四角形のみ正しく描画するため、分割された三角形はそのままでは
  使えません。全面を四角形にしてからエクスポートしてください）

### 軸変換（常時有効・固定）
頂点座標・Node位置の両方に **X軸+90度回転** を常に適用します。
これによりBlender上の向きとゲーム内の向きが一致します。

---

## 6. モデル作成時の制約

| 項目 | 制約 |
|---|---|
| 面の形状 | **四角形のみ。** 三角形を混ぜると描画がバグる（市販版3,341面すべて四角形） |
| ポリゴン数 | **四角形512面（三角形換算1024）が目安。** 超えるとVRAM破壊級のバグが出る |
| ノード数 | **4個固定。** 増減・入れ替え不可 |
| 描画順 | Node Index が小さいほど優先。タイヤ(1〜3)はボディ(0)より必ず後ろ |

---

## 7. 未確定・要検証のパラメータ

- 座標スケール（Position Scale）
- Node position/rotation の角度換算（現状12bit角度 0-4095 = 0-360度と仮定。
  市販版は全て `(0,0,0)` のため実証できていません）
- TexPage bit9-10 / bit12-15

---

## ファイル構成
```
io_export_rcardt/
├── __init__.py         # アドオン登録
├── rcardt_format.py    # バイナリ構造体の pack/unpack
├── rcardt_presets.py   # clut_presets.json の読み込み
├── rcardt_props.py     # シーン/オブジェクト/マテリアルのプロパティ定義
├── rcardt_editor.py    # UIパネル
├── export_rcardt.py    # エクスポート
└── import_rcardt.py    # インポート
```
