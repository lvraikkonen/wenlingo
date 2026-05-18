import { use } from "react";
import { ConstructionState } from "../../../../components/ConstructionState";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";

export default function ReadingPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
        <ConstructionState
          title="阅读峡谷施工中"
          body="这里还在建设。小文星球会先把今天推荐的作文和句子任务陪你做好。"
          primaryHref={`/children/${studentId}`}
          secondaryHref={`/children/${studentId}/sentence`}
        />
      </main>
    </>
  );
}
