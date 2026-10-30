import History from "./History.jsx";
import { PageHeader } from "../components/ui";

export default function Reports() {
  return <History reportsMode><PageHeader title="Reports" subtitle="Completed analyses. Open one and choose “Download report” for the PDF; it is generated on demand from the stored results." /></History>;
}
