export type TitleRewriteMode = "minimal" | "full_h1" | "full_all" | "mixed";
export const titleRewriteOptions: { value: TitleRewriteMode; label: string; keywords: string }[] = [
 {value:"minimal",label:"Точечно: Title и H1",keywords:"текущий режим минимально"},
 {value:"full_h1",label:"Полностью: Title и H1",keywords:"полное переписывание"},
 {value:"full_all",label:"Полностью: Title и все заголовки H1–H6",keywords:"полное переписывание h2 h3 h4 h5 h6"},
 {value:"mixed",label:"Смешанный: все три способа поровну",keywords:"равномерно точечно полностью h1 h2 h3 h4 h5 h6"},
];
export const titleRewriteLabel = (mode:TitleRewriteMode) => titleRewriteOptions.find(option=>option.value===mode)?.label || titleRewriteOptions[0].label;
