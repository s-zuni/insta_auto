import type { Channel, StyleId } from "./types";

/** 스타일 id 는 apps/agent/generators/matrix_prompt.py STYLE_MATRIX 와 동일해야 함 */
export const STYLES: { id: StyleId; label: string; desc: string; emoji: string }[] = [
  { id: "info", label: "꿀팁·정보형", desc: "몰랐던 정보를 3가지로 압축", emoji: "💡" },
  { id: "story", label: "스토리텔링형", desc: "가게 이야기로 공감 얻기", emoji: "📖" },
  { id: "review", label: "후기·사례형", desc: "실제 변화로 신뢰 만들기", emoji: "⭐" },
  { id: "promo", label: "프로모션형", desc: "혜택·기간을 분명하게", emoji: "🎁" },
  { id: "empathy", label: "고민공감형", desc: "손님 고민에서 출발", emoji: "🤝" },
];

/** 업종별 추천 주제 */
export const INDUSTRIES: { id: string; label: string; topics: string[] }[] = [
  { id: "cafe", label: "카페", topics: ["원두 보관법", "시그니처 메뉴 소개", "디카페인 오해와 진실", "신메뉴 출시"] },
  { id: "restaurant", label: "음식점", topics: ["사장님이 고르는 식재료 기준", "점심 특선 안내", "단체 예약 꿀팁", "대표 메뉴 맛있게 먹는 법"] },
  { id: "beauty", label: "미용실", topics: ["손상모 관리 루틴", "얼굴형별 헤어 추천", "펌 후 관리법", "첫 방문 할인 이벤트"] },
  { id: "shop", label: "온라인 쇼핑몰", topics: ["이번 주 신상 소개", "사이즈 고르는 법", "배송·교환 안내", "리뷰 베스트 모음"] },
  { id: "edu", label: "학원·교육", topics: ["우리 아이 공부 습관 만들기", "상담 신청 안내", "수강생 성장 사례", "방학 특강 소개"] },
  { id: "fitness", label: "헬스·필라테스", topics: ["초보자 운동 루틴", "체험 수업 안내", "자세 교정 팁", "회원 변화 후기"] },
];

export const CHANNELS: { id: Channel; label: string; needs: string }[] = [
  { id: "instagram", label: "인스타그램 릴스", needs: "영상" },
  { id: "youtube", label: "유튜브 쇼츠", needs: "영상" },
  { id: "threads", label: "쓰레드", needs: "텍스트" },
  { id: "naver_blog", label: "네이버 블로그", needs: "원고" },
];
