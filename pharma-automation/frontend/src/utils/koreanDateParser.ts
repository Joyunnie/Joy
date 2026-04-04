export interface ParseResult {
  title: string;
  dueDate: Date | null;
  dueTime: string | null; // "HH:mm"
  highlights: Array<{
    start: number;
    end: number;
    type: "date" | "time";
    parsed: string;
  }>;
}

interface MatchResult {
  start: number;
  end: number;
  type: "date" | "time";
  parsed: string;
  apply: (base: Date) => Date;
}

const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];

function getNextWeekday(base: Date, targetDay: number): Date {
  const current = base.getDay();
  let diff = targetDay - current;
  if (diff <= 0) diff += 7;
  const result = new Date(base);
  result.setDate(result.getDate() + diff);
  return result;
}

function getMondayOfWeek(base: Date, weeksAhead: number): Date {
  const current = base.getDay();
  // Monday = 1
  let diffToMonday = 1 - current;
  if (diffToMonday > 0) diffToMonday -= 7; // go back to this week's Monday
  const result = new Date(base);
  result.setDate(result.getDate() + diffToMonday + weeksAhead * 7);
  return result;
}

function getFirstOfMonth(base: Date, monthsAhead: number): Date {
  const result = new Date(base);
  result.setMonth(result.getMonth() + monthsAhead, 1);
  return result;
}

export function parseKoreanDate(input: string, baseDate?: Date): ParseResult {
  const base = baseDate ? new Date(baseDate) : new Date();
  // Normalize base to start of day
  base.setHours(0, 0, 0, 0);

  const matches: MatchResult[] = [];

  // --- DATE PATTERNS (order: longest/most specific first) ---

  // 1. Full absolute date: 2026년 5월 10일
  const fullDateRe = /(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일/g;
  let m: RegExpExecArray | null;
  while ((m = fullDateRe.exec(input)) !== null) {
    const year = parseInt(m[1]);
    const month = parseInt(m[2]);
    const day = parseInt(m[3]);
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      apply: () => {
        const d = new Date(base);
        d.setFullYear(year, month - 1, day);
        return d;
      },
    });
  }

  // 2. Month+day: 5월 10일
  const monthDayRe = /(?<!\d{4}년\s*)(\d{1,2})월\s*(\d{1,2})일/g;
  while ((m = monthDayRe.exec(input)) !== null) {
    // Skip if already matched by full date
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const month = parseInt(m[1]);
    const day = parseInt(m[2]);
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      apply: () => {
        const d = new Date(base);
        d.setMonth(month - 1, day);
        if (d < base) d.setFullYear(d.getFullYear() + 1);
        return d;
      },
    });
  }

  // 3. Slash date: 12/25 or 5/10
  const slashDateRe = /(?<!\d)(\d{1,2})\/(\d{1,2})(?!\d)/g;
  while ((m = slashDateRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const month = parseInt(m[1]);
    const day = parseInt(m[2]);
    if (month < 1 || month > 12 || day < 1 || day > 31) continue;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      apply: () => {
        const d = new Date(base);
        d.setMonth(month - 1, day);
        if (d < base) d.setFullYear(d.getFullYear() + 1);
        return d;
      },
    });
  }

  // 4. "다다음주 X요일" / "다음주 X요일" / "이번주 X요일"
  const weekDayComboRe = /(다다음주|다음주|이번주)\s*([월화수목금토일])요일(까지)?/g;
  while ((m = weekDayComboRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const weekPrefix = m[1];
    const dayChar = m[2];
    const dayIdx = DAY_NAMES.indexOf(dayChar);
    const weeksAhead =
      weekPrefix === "이번주" ? 0 : weekPrefix === "다음주" ? 1 : 2;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${weekPrefix} ${dayChar}요일`,
      apply: () => {
        const monday = getMondayOfWeek(base, weeksAhead);
        const result = new Date(monday);
        // dayIdx: 일=0,월=1,...토=6 but our getMondayOfWeek gives Monday
        // Monday=1 in DAY_NAMES, so offset from Monday = dayIdx - 1, but Sunday(0) = +6
        const offset = dayIdx === 0 ? 6 : dayIdx - 1;
        result.setDate(result.getDate() + offset);
        return result;
      },
    });
  }

  // 5. Standalone weekday: "월요일" ~ "일요일" (with optional 까지)
  // Must NOT match single char like 화 in 화장품
  const weekdayRe = /([월화수목금토일])요일(까지)?/g;
  while ((m = weekdayRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const dayChar = m[1];
    const dayIdx = DAY_NAMES.indexOf(dayChar);
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${dayChar}요일`,
      apply: () => getNextWeekday(base, dayIdx),
    });
  }

  // 6. "다다음달 15일" / "다음달 15일" / "이번달 15일"
  const monthDayComboRe = /(다다음달|다음달|이번달)\s*(\d{1,2})일/g;
  while ((m = monthDayComboRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const monthPrefix = m[1];
    const day = parseInt(m[2]);
    const monthsAhead =
      monthPrefix === "이번달" ? 0 : monthPrefix === "다음달" ? 1 : 2;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${monthPrefix} ${day}일`,
      apply: () => {
        const d = getFirstOfMonth(base, monthsAhead);
        d.setDate(day);
        return d;
      },
    });
  }

  // 7. "다다음주" / "다음주" / "이번주" (standalone, → Monday)
  const weekOnlyRe = /(다다음주|다음주|이번주)(?!\s*[월화수목금토일])/g;
  while ((m = weekOnlyRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const prefix = m[1];
    const weeksAhead = prefix === "이번주" ? 0 : prefix === "다음주" ? 1 : 2;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${prefix} 월요일`,
      apply: () => getMondayOfWeek(base, weeksAhead),
    });
  }

  // 8. "다다음달" / "다음달" / "이번달" (standalone, → 1st)
  const monthOnlyRe = /(다다음달|다음달|이번달)(?!\s*\d)/g;
  while ((m = monthOnlyRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const prefix = m[1];
    const monthsAhead = prefix === "이번달" ? 0 : prefix === "다음달" ? 1 : 2;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: `${prefix} 1일`,
      apply: () => getFirstOfMonth(base, monthsAhead),
    });
  }

  // 9. Relative days: 오늘/내일/모레/글피/어제/그저께
  const relativeDayMap: Record<string, number> = {
    오늘: 0,
    내일: 1,
    모레: 2,
    글피: 3,
    어제: -1,
    그저께: -2,
  };
  const relativeDayRe = /(오늘|내일|모레|글피|어제|그저께)/g;
  while ((m = relativeDayRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const word = m[1];
    const offset = relativeDayMap[word];
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "date",
      parsed: word,
      apply: () => {
        const d = new Date(base);
        d.setDate(d.getDate() + offset);
        return d;
      },
    });
  }

  // --- TIME PATTERNS ---

  // 1. 오전/오후 + 시 + 분
  const ampmTimeRe = /(오전|오후)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?/g;
  while ((m = ampmTimeRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const ampm = m[1];
    let hour = parseInt(m[2]);
    const min = m[3] ? parseInt(m[3]) : 0;
    if (ampm === "오후" && hour < 12) hour += 12;
    if (ampm === "오전" && hour === 12) hour = 0;
    const timeStr = `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "time",
      parsed: timeStr,
      apply: (d) => {
        d.setHours(hour, min, 0, 0);
        return d;
      },
    });
  }

  // 2. X시 Y분 (without 오전/오후)
  const timeHMRe = /(?<!오[전후]\s*)(\d{1,2})시(?:\s*(\d{1,2})분)?/g;
  while ((m = timeHMRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const hour = parseInt(m[1]);
    const min = m[2] ? parseInt(m[2]) : 0;
    const timeStr = `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "time",
      parsed: timeStr,
      apply: (d) => {
        d.setHours(hour, min, 0, 0);
        return d;
      },
    });
  }

  // 3. HH:MM format (24h)
  const colonTimeRe = /(?<!\d)(\d{1,2}):(\d{2})(?!\d)/g;
  while ((m = colonTimeRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    // Avoid matching slash dates like 12/25
    const hour = parseInt(m[1]);
    const min = parseInt(m[2]);
    if (hour > 23 || min > 59) continue;
    const timeStr = `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "time",
      parsed: timeStr,
      apply: (d) => {
        d.setHours(hour, min, 0, 0);
        return d;
      },
    });
  }

  // 4. Named times: 아침/점심/저녁/밤
  const namedTimeMap: Record<string, string> = {
    아침: "09:00",
    점심: "12:00",
    저녁: "18:00",
    밤: "21:00",
  };
  const namedTimeRe = /(아침|점심|저녁|밤)/g;
  while ((m = namedTimeRe.exec(input)) !== null) {
    if (matches.some((prev) => m!.index >= prev.start && m!.index < prev.end)) continue;
    const word = m[1];
    const timeStr = namedTimeMap[word];
    const [h, mi] = timeStr.split(":").map(Number);
    matches.push({
      start: m.index,
      end: m.index + m[0].length,
      type: "time",
      parsed: timeStr,
      apply: (d) => {
        d.setHours(h, mi, 0, 0);
        return d;
      },
    });
  }

  // --- BUILD RESULT ---

  // Sort matches by position
  matches.sort((a, b) => a.start - b.start);

  // Separate date and time matches
  const dateMatches = matches.filter((m) => m.type === "date");
  const timeMatches = matches.filter((m) => m.type === "time");

  let dueDate: Date | null = null;
  let dueTime: string | null = null;

  if (dateMatches.length > 0) {
    dueDate = dateMatches[0].apply(new Date(base));
  }

  if (timeMatches.length > 0) {
    dueTime = timeMatches[0].parsed;
    if (dueDate) {
      timeMatches[0].apply(dueDate);
    } else {
      // Time without date → today
      dueDate = new Date(base);
      timeMatches[0].apply(dueDate);
    }
  }

  // Build title: remove matched portions and clean up
  const allMatches = [...dateMatches, ...timeMatches].sort(
    (a, b) => a.start - b.start
  );
  let title = input;
  // Remove from end to start to preserve indices
  for (let i = allMatches.length - 1; i >= 0; i--) {
    const match = allMatches[i];
    title = title.slice(0, match.start) + title.slice(match.end);
  }
  // Clean up whitespace
  title = title.replace(/\s+/g, " ").trim();

  // Build highlights
  const highlights = allMatches.map((m) => ({
    start: m.start,
    end: m.end,
    type: m.type,
    parsed: m.parsed,
  }));

  return {
    title,
    dueDate,
    dueTime,
    highlights,
  };
}
