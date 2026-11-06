export type GeneratedMenuStructureItem = {
  title: string;
  slug: string;
  content_kind: "menu_page" | "casino_review" | "technical_page";
  technical_page_key?: string;
  parent_slug?: string;
  children?: GeneratedMenuStructureItem[];
};
export type PreviewNode = { item: GeneratedMenuStructureItem; path: string; parent: string; depth: number };
export function previewNodes(items: GeneratedMenuStructureItem[], parent = "", depth = 1): PreviewNode[] {
  return items.flatMap((item, index) => {
    const path = parent ? `${parent}.${index}` : String(index);
    return [{ item, path, parent, depth }, ...previewNodes(item.children || [], path, depth + 1)];
  });
}
export function previewDepth(items: GeneratedMenuStructureItem[]): number {
  return Math.max(1, ...previewNodes(items).map(node => node.depth));
}
export function editPreviewItem(items: GeneratedMenuStructureItem[], path: string, patch: Partial<GeneratedMenuStructureItem> | null) {
  const copy = structuredClone(items);
  const indices = path.split('.').map(Number);
  let siblings = copy;
  for (const index of indices.slice(0, -1)) siblings = siblings[index].children || [];
  const index = indices[indices.length - 1];
  if (patch) Object.assign(siblings[index], patch); else siblings.splice(index, 1);
  return copy;
}
export function movePreviewItem(items: GeneratedMenuStructureItem[], path: string, parent: string) {
  const copy = structuredClone(items);
  const nodes = previewNodes(copy);
  const source = nodes.find(node => node.path === path);
  const target = nodes.find(node => node.path === parent);
  if (!source || parent === path || parent.startsWith(`${path}.`) || (parent && !target)) return items;
  if (parent === source.parent) return items;
  if ((target?.depth || 0) + previewDepth([source.item]) > 3) return items;
  const previous = nodes.find(node => node.path === source.parent);
  const siblings = previous ? previous.item.children || [] : copy;
  siblings.splice(siblings.indexOf(source.item), 1);
  const destination = target ? (target.item.children ||= []) : copy;
  const oldSlug = source.item.slug;
  const segment = oldSlug.split('/').filter(Boolean).pop() || 'page';
  const newSlug = `${target?.item.slug.replace(/\/$/, '') || ''}/${segment}/`;
  for (const node of previewNodes([source.item])) {
    if (node.item.slug.startsWith(oldSlug)) node.item.slug = newSlug + node.item.slug.slice(oldSlug.length);
  }
  destination.push(source.item);
  return copy;
}
