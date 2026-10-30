package io.github.dtingley11.letappslive;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/** Install-time CLI used by the module; not invoked by the app UI or at boot. */
public final class PolicyCompiler {
    private static final int MAX_XML_BYTES = 2 * 1024 * 1024;

    private PolicyCompiler() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 7) throw new IOException("Expected original, base, downloaded base/custom, visible policy, inventory and output paths.");
        Path original = Paths.get(args[0]);
        Document stock = parse(read(original));
        Document base = parse(read(Paths.get(args[1])));
        validate(stock, "sys_custom_clear_appfilter_list");
        validate(base, "sys_clear_appfilter_list");
        Document downloadedBase = remote(Paths.get(args[2]), "sys_clear_appfilter_list");
        Document downloadedCustom = remote(Paths.get(args[3]), "sys_custom_clear_appfilter_list");
        Document visible = parse(read(Paths.get(args[4])));
        validate(visible, "sys_custom_clear_appfilter_list");
        if (downloadedBase != null && version(downloadedBase) > version(base)) base = downloadedBase;
        Document custom = downloadedCustom != null && version(downloadedCustom) > version(stock)
                ? downloadedCustom : stock;
        long next = Math.max(version(custom), version(visible)) + 1;
        if (next > Integer.MAX_VALUE) throw new IOException("The custom policy version cannot be incremented.");

        Map<String, Element> normal = new TreeMap<>();
        Map<String, Element> conditional = new TreeMap<>();
        boolean supportsKill = false;
        for (Element rule : children(base.getDocumentElement())) {
            if (!isRule(rule)) continue;
            checkRule(rule);
            supportsKill |= rule.hasAttribute("use_kill");
            String pkg = rule.getAttribute("pkg");
            if (!validPackage(pkg)) continue;
            (rule.getTagName().equals("p_cond_wl") ? conditional : normal).put(pkg, rule);
        }
        if (!supportsKill) throw new IOException("The native Athena policy does not expose use_kill rules.");
        for (Element rule : children(custom.getDocumentElement())) if (isRule(rule)) checkRule(rule);
        normal.putAll(conditional);
        StringBuilder templates = new StringBuilder();
        for (Map.Entry<String, Element> entry : normal.entrySet()) {
            Element copy = (Element) entry.getValue().cloneNode(true);
            copy.setAttribute("use_kill", "true");
            templates.append(entry.getKey()).append('\t').append(xml(copy)).append('\n');
        }
        Path output = Paths.get(args[6]);
        Files.createDirectories(output);
        Files.copy(original, output.resolve("original-custom.xml"), StandardCopyOption.REPLACE_EXISTING);
        write(output.resolve("custom-policy.xml"), normalized(custom));
        write(output.resolve("policy-entries.tsv"), templates.toString());
        write(output.resolve("policy-version.txt"), next + "\n");
        write(output.resolve("source-versions.txt"), "base=" + version(base) + "\ncustom=" + version(custom) + "\n");
        // Validate the selected inventory before publishing prepared configuration.
        String last = null;
        for (String pkg : Files.readAllLines(Paths.get(args[5]))) {
            if (!validPackage(pkg) || !pkg.contains(".") || last != null && last.compareTo(pkg) >= 0)
                throw new IOException("The user-app inventory is invalid.");
            last = pkg;
        }
        System.out.println("Prepared device policy: base " + version(base) + ", custom " + next + ".");
    }

    static String read(Path path) throws IOException {
        if (Files.size(path) > MAX_XML_BYTES) throw new IOException("Policy file is too large.");
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }

    static void write(Path path, String text) throws IOException {
        Files.write(path, text.getBytes(StandardCharsets.UTF_8));
    }

    static Document parse(String text) throws Exception {
        if (text.getBytes(StandardCharsets.UTF_8).length > MAX_XML_BYTES
                || text.contains("<!DOCTYPE") || text.contains("<!ENTITY"))
            throw new IOException("Unsupported XML declarations or policy size.");
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setExpandEntityReferences(false);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));
    }

    static Document remote(Path path, String filter) throws Exception {
        String raw = read(path).trim();
        if (raw.equals("No result found.") || raw.equals("No result found") || raw.matches("Row: 0 xml=null")) return null;
        int start = raw.indexOf('<');
        if (start < 0) throw new IOException("Downloaded policy query did not return XML or an empty result.");
        String prefix = raw.substring(0, start).trim();
        if (!prefix.isEmpty() && !prefix.matches("Row: 0 xml="))
            throw new IOException("Unexpected downloaded policy query format.");
        Document result = parse(raw.substring(start));
        validate(result, filter);
        return result;
    }

    static void validate(Document document, String filter) throws Exception {
        Element root = document.getDocumentElement();
        if (!root.getTagName().equals("filter-conf") || !text(root, "filter-name").equals(filter)
                || !text(root, "isOpen").equals("1"))
            throw new IOException("The native cleanup filter format is unsupported or disabled.");
        version(document);
    }

    static String text(Element root, String name) throws IOException {
        String result = null;
        for (Element child : children(root)) if (child.getTagName().equals(name)) {
            if (result != null) throw new IOException("Duplicate " + name + " field.");
            result = child.getTextContent().trim();
        }
        if (result == null) throw new IOException("Missing " + name + " field.");
        return result;
    }

    static long version(Document document) throws Exception {
        String value = text(document.getDocumentElement(), "version");
        if (!value.matches("[0-9]+")) throw new IOException("Invalid policy version.");
        long result = Long.parseLong(value);
        if (result < 1 || result > Integer.MAX_VALUE) throw new IOException("Unsupported policy version range.");
        return result;
    }

    static boolean validPackage(String pkg) {
        return pkg.matches("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*");
    }

    static boolean isRule(Element node) {
        return node.getTagName().equals("p_wl") || node.getTagName().equals("p_crm") || node.getTagName().equals("p_cond_wl");
    }

    static void checkRule(Element rule) throws IOException {
        if (!rule.hasAttribute("pkg") || !children(rule).isEmpty() || !rule.getTextContent().trim().isEmpty())
            throw new IOException("Unsupported nested cleanup rule.");
    }

    static List<Element> children(Element node) {
        List<Element> result = new ArrayList<>();
        for (Node child = node.getFirstChild(); child != null; child = child.getNextSibling())
            if (child instanceof Element) result.add((Element) child);
        return result;
    }

    static String xml(Node node) throws Exception {
        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
        transformer.setOutputProperty(OutputKeys.INDENT, "no");
        StringWriter writer = new StringWriter();
        transformer.transform(new DOMSource(node), new StreamResult(writer));
        return writer.toString();
    }

    static String normalized(Document document) throws Exception {
        Element root = document.getDocumentElement();
        Element empty = (Element) root.cloneNode(false);
        String opening = xml(empty);
        if (!opening.endsWith("/>")) throw new IOException("Unsupported policy root.");
        StringBuilder result = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        result.append(opening, 0, opening.length() - 2).append(">\n");
        for (Node child = root.getFirstChild(); child != null; child = child.getNextSibling()) {
            if (child.getNodeType() == Node.TEXT_NODE && child.getTextContent().trim().isEmpty()) continue;
            result.append("    ").append(xml(child)).append('\n');
        }
        return result.append("</filter-conf>\n").toString();
    }
}
