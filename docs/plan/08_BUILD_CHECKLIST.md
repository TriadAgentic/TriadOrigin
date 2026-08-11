# 08 · Generated Closure Checklist

_Mechanical projection. Do not edit; run `python tools/closure_control.py --write`._

Safety baseline: `OFF / OFF / OFF / LIVE`. No deployment, restart, MCP enablement, arming, order action, venue mutation, or promotion is authorized.

## `CONTROL_FREEZE::C0::sha256:3a2152de236540099955b21e9efef846775d1aee0d15af86eafabecb954cc230`

- [ ] `ANCHOR::C0` — required protected anchor is not published (provenance: `PATH_LAW:C0_CONTROL_DIGEST`)
- [ ] `C0-EXACT-HEAD-REVIEW` — C0 exact-head source review is UNBOUND (provenance: `SEMANTICS_BLOCKER_CATALOG:review_policy:SOURCE_REVIEWER`)
- [ ] `C0-OWNER-AUTH` — C0 owner authentication is UNBOUND (provenance: `SEMANTICS_BLOCKER_CATALOG:review_policy:C0_OWNER_AUTHENTICATOR`)
- [ ] `LEGACY_B00_REALLOCATION_REQUIRED` — legacy B00 tasks require explicit owner reallocation (provenance: `SEMANTICS_BLOCKER_CATALOG:closure_task_bindings.v1.json`)
- [ ] `RECEIPT::C0` — required evidence-only receipt is not merged (provenance: `PATH_LAW:NOT_APPLICABLE_CONTROL_FREEZE`)
- [ ] `REVIEW-SLOT::C0::C0_OWNER_AUTHENTICATOR` — C0_OWNER_AUTHENTICATOR provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:CONTROL_FREEZE::C0::sha256:3a2152de236540099955b21e9efef846775d1aee0d15af86eafabecb954cc230:C0_OWNER_AUTHENTICATOR`)
- [ ] `REVIEW-SLOT::C0::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:CONTROL_FREEZE::C0::sha256:3a2152de236540099955b21e9efef846775d1aee0d15af86eafabecb954cc230:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::C0::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:CONTROL_FREEZE::C0::sha256:3a2152de236540099955b21e9efef846775d1aee0d15af86eafabecb954cc230:SOURCE_REVIEWER`)

## `ORIGIN_REPAIR::B00R_G2::sha256:71b011d46c6a7ebd092bda6d2d303572c9a44508bd126ff9a50e2e5bad40eaf5`

- [ ] `ANCHOR::B00R_G2` — required protected anchor is not published (provenance: `PATH_LAW:B00R_RECEIPT_ANCHOR_G2`)
- [ ] `B00R-G2-AUTHORITY-PINS` — four authenticated G2 authority pins are absent (provenance: `SEMANTICS_BLOCKER_CATALOG:D-02`)
- [ ] `B00R-G2-CANARY` — rejected negative canary is NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:T6`)
- [ ] `B00R-G2-EXACT-HEAD-REVIEW` — B00R G2 exact-head review is UNBOUND (provenance: `SEMANTICS_BLOCKER_CATALOG:review_policy:SOURCE_REVIEWER`)
- [ ] `B00R-G2-RECEIPT-ANCHOR` — evidence-only receipt merge and protected anchor are absent (provenance: `SEMANTICS_BLOCKER_CATALOG:T7`)
- [ ] `B00R-G2-RULESET` — real live provider ruleset capture and external pin are NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:T6`)
- [ ] `PREDECESSOR::B00R_G2` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:CONTROL_FREEZE::C0::sha256:3a2152de236540099955b21e9efef846775d1aee0d15af86eafabecb954cc230`)
- [ ] `RECEIPT::B00R_G2` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B00R.g2.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B00R_G2::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B00R_G2::sha256:71b011d46c6a7ebd092bda6d2d303572c9a44508bd126ff9a50e2e5bad40eaf5:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B00R_G2::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B00R_G2::sha256:71b011d46c6a7ebd092bda6d2d303572c9a44508bd126ff9a50e2e5bad40eaf5:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B00R_G2` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B01C::sha256:7d6e36d32db8e3eee19aa6fd446bdc48644f70916ef09d939f113f19c5a6db5e`

- [ ] `ANCHOR::B01C` — required protected anchor is not published (provenance: `PATH_LAW:B01C_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B01C` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B00R_G2::sha256:71b011d46c6a7ebd092bda6d2d303572c9a44508bd126ff9a50e2e5bad40eaf5`)
- [ ] `RECEIPT::B01C` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B01C.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B01C::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B01C::sha256:7d6e36d32db8e3eee19aa6fd446bdc48644f70916ef09d939f113f19c5a6db5e:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B01C::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B01C::sha256:7d6e36d32db8e3eee19aa6fd446bdc48644f70916ef09d939f113f19c5a6db5e:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B01C` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B02C::sha256:b39df55b17320f8638d440ecada4dcfd35ff631fb9006f5a5acdce33207bda27`

- [ ] `ANCHOR::B02C` — required protected anchor is not published (provenance: `PATH_LAW:B02C_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B02C` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B01C::sha256:7d6e36d32db8e3eee19aa6fd446bdc48644f70916ef09d939f113f19c5a6db5e`)
- [ ] `RECEIPT::B02C` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B02C.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B02C::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B02C::sha256:b39df55b17320f8638d440ecada4dcfd35ff631fb9006f5a5acdce33207bda27:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B02C::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B02C::sha256:b39df55b17320f8638d440ecada4dcfd35ff631fb9006f5a5acdce33207bda27:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B02C` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B03C::sha256:fb31fc7a907297c0efe67d88e926ed744c2d7753536d3ddf858ada6778a0b8ec`

- [ ] `ANCHOR::B03C` — required protected anchor is not published (provenance: `PATH_LAW:B03C_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B03C` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B02C::sha256:b39df55b17320f8638d440ecada4dcfd35ff631fb9006f5a5acdce33207bda27`)
- [ ] `RECEIPT::B03C` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B03C.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B03C::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B03C::sha256:fb31fc7a907297c0efe67d88e926ed744c2d7753536d3ddf858ada6778a0b8ec:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B03C::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B03C::sha256:fb31fc7a907297c0efe67d88e926ed744c2d7753536d3ddf858ada6778a0b8ec:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B03C` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B04C::sha256:f9f42e48fc0a642b16a2512854a39acd595e9f45070db4580db487eaaca274c2`

- [ ] `ANCHOR::B04C` — required protected anchor is not published (provenance: `PATH_LAW:B04C_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B04C` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B03C::sha256:fb31fc7a907297c0efe67d88e926ed744c2d7753536d3ddf858ada6778a0b8ec`)
- [ ] `RECEIPT::B04C` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B04C.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B04C::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B04C::sha256:f9f42e48fc0a642b16a2512854a39acd595e9f45070db4580db487eaaca274c2:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B04C::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B04C::sha256:f9f42e48fc0a642b16a2512854a39acd595e9f45070db4580db487eaaca274c2:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B04C` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B05C::sha256:d05dd3facf362c71aec3a66e344962a0bf7a76cf0ee8c63fe14fb05f717c6c22`

- [ ] `ANCHOR::B05C` — required protected anchor is not published (provenance: `PATH_LAW:B05C_RECEIPT_ANCHOR`)
- [ ] `B05-AUTHORIZATION` — deployment and restart remain unauthorized (provenance: `SEMANTICS_BLOCKER_CATALOG:D-08`)
- [ ] `B05-CREDENTIAL-ROTATION` — D-09 credential rotation is NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:D-09`)
- [ ] `B05-PHYSICAL-ISOLATION-SOAK` — physical four-plane isolation and 24-hour SHADOW soak are NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:T8:T9`)
- [ ] `PREDECESSOR::B05C` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B04C::sha256:f9f42e48fc0a642b16a2512854a39acd595e9f45070db4580db487eaaca274c2`)
- [ ] `RECEIPT::B05C` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B05C.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B05C::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B05C::sha256:d05dd3facf362c71aec3a66e344962a0bf7a76cf0ee8c63fe14fb05f717c6c22:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B05C::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B05C::sha256:d05dd3facf362c71aec3a66e344962a0bf7a76cf0ee8c63fe14fb05f717c6c22:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B05C` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B06R::sha256:b851e656d1e01bd2ba1705d47c93ff4551f4ffd2842939b807ab486f76fcde2d`

- [ ] `ANCHOR::B06R` — required protected anchor is not published (provenance: `PATH_LAW:B06R_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B06R` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B05C::sha256:d05dd3facf362c71aec3a66e344962a0bf7a76cf0ee8c63fe14fb05f717c6c22`)
- [ ] `RECEIPT::B06R` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B06R.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B06R::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B06R::sha256:b851e656d1e01bd2ba1705d47c93ff4551f4ffd2842939b807ab486f76fcde2d:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B06R::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B06R::sha256:b851e656d1e01bd2ba1705d47c93ff4551f4ffd2842939b807ab486f76fcde2d:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B06R` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B07::sha256:2d5ebad6dc68cf908d1a26f161f4d5870fe585c4cbca8a8b7e9d998cd8150bef`

- [ ] `ANCHOR::B07` — required protected anchor is not published (provenance: `PATH_LAW:B07_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B07` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B06R::sha256:b851e656d1e01bd2ba1705d47c93ff4551f4ffd2842939b807ab486f76fcde2d`)
- [ ] `RECEIPT::B07` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B07.receipt.v3.json`)
- [ ] `REVIEW-SLOT::B07::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B07::sha256:2d5ebad6dc68cf908d1a26f161f4d5870fe585c4cbca8a8b7e9d998cd8150bef:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B07::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B07::sha256:2d5ebad6dc68cf908d1a26f161f4d5870fe585c4cbca8a8b7e9d998cd8150bef:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B07` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ESTATE_CROSS_REPO::XC01::sha256:70a8eb8cf39df88c508f2469a936ba1e926ed6bc84d608c5ff5b9dc913db3ca8`

- [ ] `ANCHOR::XC01` — required protected anchor is not published (provenance: `PATH_LAW:XC01_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::XC01` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B07::sha256:2d5ebad6dc68cf908d1a26f161f4d5870fe585c4cbca8a8b7e9d998cd8150bef`)
- [ ] `RECEIPT::XC01` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/XC01.receipt.v4.json`)
- [ ] `REVIEW-SLOT::XC01::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ESTATE_CROSS_REPO::XC01::sha256:70a8eb8cf39df88c508f2469a936ba1e926ed6bc84d608c5ff5b9dc913db3ca8:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::XC01::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ESTATE_CROSS_REPO::XC01::sha256:70a8eb8cf39df88c508f2469a936ba1e926ed6bc84d608c5ff5b9dc913db3ca8:SOURCE_REVIEWER`)
- [ ] `RUNTIME::XC01` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)
- [ ] `XC01-OWNER-RECEIPTS` — owner-repository receipt slots are UNBOUND and NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:XC01_ACCEPTANCE_PROFILE_V1`)

## `ORIGIN_REPAIR::B08::sha256:4bf3e75b3c4de3c0f997f2191551afd5dbd39b452658eff5e3f9e67416b9f83f`

- [ ] `ANCHOR::B08` — required protected anchor is not published (provenance: `PATH_LAW:B08_RECEIPT_ANCHOR`)
- [ ] `PREDECESSOR::B08` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ESTATE_CROSS_REPO::XC01::sha256:70a8eb8cf39df88c508f2469a936ba1e926ed6bc84d608c5ff5b9dc913db3ca8`)
- [ ] `RECEIPT::B08` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B08.receipt.v4.json`)
- [ ] `REVIEW-SLOT::B08::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B08::sha256:4bf3e75b3c4de3c0f997f2191551afd5dbd39b452658eff5e3f9e67416b9f83f:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B08::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B08::sha256:4bf3e75b3c4de3c0f997f2191551afd5dbd39b452658eff5e3f9e67416b9f83f:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B08` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B09::sha256:00773cb7d61c85d047cbd2c828c9f0324476d6fb0701b7019541ccc24bae3407`

- [ ] `ANCHOR::B09` — required protected anchor is not published (provenance: `PATH_LAW:B09_RECEIPT_ANCHOR`)
- [ ] `B09-CONFORMANCE-DR` — unique conformance and disaster-recovery owner proofs are NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:T10:T11`)
- [ ] `PREDECESSOR::B09` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B08::sha256:4bf3e75b3c4de3c0f997f2191551afd5dbd39b452658eff5e3f9e67416b9f83f`)
- [ ] `RECEIPT::B09` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B09.receipt.v4.json`)
- [ ] `REVIEW-SLOT::B09::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B09::sha256:00773cb7d61c85d047cbd2c828c9f0324476d6fb0701b7019541ccc24bae3407:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B09::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B09::sha256:00773cb7d61c85d047cbd2c828c9f0324476d6fb0701b7019541ccc24bae3407:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B09` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25`

- [ ] `ANCHOR::B10` — required protected anchor is not published (provenance: `PATH_LAW:B10_RECEIPT_ANCHOR`)
- [ ] `B10-CREDENTIAL-GATE` — D-09 credential rotation/security gate is NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:D-09`)
- [ ] `B10-FROZEN-SUBJECT` — B10 terminal subject registry is not frozen (provenance: `SEMANTICS_BLOCKER_CATALOG:b10_terminal_control`)
- [ ] `B10-TWO-AUDITS` — two distinct B10 auditor slots and adjudicator are UNBOUND (provenance: `SEMANTICS_BLOCKER_CATALOG:b10_terminal_control`)
- [ ] `PREDECESSOR::B10` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B09::sha256:00773cb7d61c85d047cbd2c828c9f0324476d6fb0701b7019541ccc24bae3407`)
- [ ] `RECEIPT::B10` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/B10.receipt.v4.json`)
- [ ] `REVIEW-SLOT::B10::B10_ADJUDICATOR` — B10_ADJUDICATOR provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25:B10_ADJUDICATOR`)
- [ ] `REVIEW-SLOT::B10::B10_RUNTIME_SIDE_EFFECT_AUDITOR` — B10_RUNTIME_SIDE_EFFECT_AUDITOR provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25:B10_RUNTIME_SIDE_EFFECT_AUDITOR`)
- [ ] `REVIEW-SLOT::B10::B10_SEMANTIC_SOURCE_AUDITOR` — B10_SEMANTIC_SOURCE_AUDITOR provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25:B10_SEMANTIC_SOURCE_AUDITOR`)
- [ ] `REVIEW-SLOT::B10::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::B10::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25:SOURCE_REVIEWER`)
- [ ] `RUNTIME::B10` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)

## `ESTATE_CLOSURE::BN::sha256:80dd0762c222cb661692896003ace482602cd028860d630d58da71a925cb79e3`

- [ ] `ANCHOR::BN` — required protected anchor is not published (provenance: `PATH_LAW:BN_TERMINAL_SAFE_HOLD_ANCHOR`)
- [ ] `BN-FRESH-AGGREGATE` — fresh identical-subject runtime and money-ledger aggregate is NOT_ATTESTED (provenance: `SEMANTICS_BLOCKER_CATALOG:D-05:T8:T10`)
- [ ] `PREDECESSOR::BN` — exact predecessor is not CLOSED (provenance: `MILESTONE_DEPENDENCY:ORIGIN_REPAIR::B10::sha256:f1d75c13f8d1cd0622738fc1d9e6f30cbc73aed0828652df1a71817f7fe06a25`)
- [ ] `RECEIPT::BN` — required evidence-only receipt is not merged (provenance: `PATH_LAW:evidence/receipts/BN.receipt.v1.json`)
- [ ] `REVIEW-SLOT::BN::RECEIPT_REVIEWER` — RECEIPT_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ESTATE_CLOSURE::BN::sha256:80dd0762c222cb661692896003ace482602cd028860d630d58da71a925cb79e3:RECEIPT_REVIEWER`)
- [ ] `REVIEW-SLOT::BN::SOURCE_REVIEWER` — SOURCE_REVIEWER provider identity is UNBOUND (provenance: `REVIEW_POLICY_SLOT:ESTATE_CLOSURE::BN::sha256:80dd0762c222cb661692896003ace482602cd028860d630d58da71a925cb79e3:SOURCE_REVIEWER`)
- [ ] `RUNTIME::BN` — applicable identical-subject runtime proof is NOT_ATTESTED (provenance: `TEST_LAYER:T8`)
