import { describe, it, expect } from "vitest";
import { parseKoreanDate } from "./koreanDateParser";

// Fixed base date: 2026-04-06 (Monday)
const BASE = new Date(2026, 3, 6); // April 6, 2026 (Monday)

function fmt(d: Date | null): string | null {
  if (!d) return null;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

describe("parseKoreanDate", () => {
  it('내일 오후 3시 도매상 전화 → tomorrow 15:00, title "도매상 전화"', () => {
    const result = parseKoreanDate("내일 오후 3시 도매상 전화", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-07");
    expect(result.dueTime).toBe("15:00");
    expect(result.title).toBe("도매상 전화");
  });

  it('다음주 월요일 재고 실사 → next monday, title "재고 실사"', () => {
    const result = parseKoreanDate("다음주 월요일 재고 실사", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-13");
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("재고 실사");
  });

  it('5월 10일 5시 30분 세미나 참석 → 5/10 17:30, title "세미나 참석"', () => {
    const result = parseKoreanDate("5월 10일 5시 30분 세미나 참석", BASE);
    expect(fmt(result.dueDate)).toBe("2026-05-10");
    expect(result.dueTime).toBe("05:30");
    expect(result.title).toBe("세미나 참석");
  });

  it('모레 약품 발주 → day+2, title "약품 발주"', () => {
    const result = parseKoreanDate("모레 약품 발주", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-08");
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("약품 발주");
  });

  it('GMP 서류 정리 → null, title "GMP 서류 정리"', () => {
    const result = parseKoreanDate("GMP 서류 정리", BASE);
    expect(result.dueDate).toBeNull();
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("GMP 서류 정리");
  });

  it('오늘 저녁 회식 → today 18:00, title "회식"', () => {
    const result = parseKoreanDate("오늘 저녁 회식", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-06");
    expect(result.dueTime).toBe("18:00");
    expect(result.title).toBe("회식");
  });

  it('다음달 15일 면허 갱신 → next month 15th, title "면허 갱신"', () => {
    const result = parseKoreanDate("다음달 15일 면허 갱신", BASE);
    expect(fmt(result.dueDate)).toBe("2026-05-15");
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("면허 갱신");
  });

  it('화요일 오전 10시 미팅 → next tuesday 10:00, title "미팅"', () => {
    const result = parseKoreanDate("화요일 오전 10시 미팅", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-07");
    expect(result.dueTime).toBe("10:00");
    expect(result.title).toBe("미팅");
  });

  it('12/25 크리스마스 파티 → 12/25, title "크리스마스 파티"', () => {
    const result = parseKoreanDate("12/25 크리스마스 파티", BASE);
    expect(fmt(result.dueDate)).toBe("2026-12-25");
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("크리스마스 파티");
  });

  it('화장품 주문 → null (오탐 방지: 단독 "화" 인식 금지)', () => {
    const result = parseKoreanDate("화장품 주문", BASE);
    expect(result.dueDate).toBeNull();
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("화장품 주문");
  });

  it('월말 정산 → null (오탐 방지: 단독 "월" 인식 금지)', () => {
    const result = parseKoreanDate("월말 정산", BASE);
    expect(result.dueDate).toBeNull();
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("월말 정산");
  });

  it('금요일까지 보고서 → friday, title "보고서"', () => {
    const result = parseKoreanDate("금요일까지 보고서", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-10");
    expect(result.dueTime).toBeNull();
    expect(result.title).toBe("보고서");
  });

  // Highlights test
  it("highlights에 date/time 타입과 위치가 정확히 나옴", () => {
    const result = parseKoreanDate("내일 오후 3시 도매상 전화", BASE);
    expect(result.highlights.length).toBe(2);
    expect(result.highlights[0].type).toBe("date");
    expect(result.highlights[1].type).toBe("time");
  });

  // Edge cases
  it("어제 → past date (no error)", () => {
    const result = parseKoreanDate("어제 보고서 마감", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-05");
    expect(result.title).toBe("보고서 마감");
  });

  it("이번주 → this week Monday", () => {
    const result = parseKoreanDate("이번주 회의", BASE);
    expect(fmt(result.dueDate)).toBe("2026-04-06");
    expect(result.title).toBe("회의");
  });

  it("다음달 → next month 1st", () => {
    const result = parseKoreanDate("다음달 정산", BASE);
    expect(fmt(result.dueDate)).toBe("2026-05-01");
    expect(result.title).toBe("정산");
  });
});
