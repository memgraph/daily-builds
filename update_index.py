import json
import os
import re
import argparse


# use this dict to map between column titles and dict keys where needed, 
# e.g. mapping `ubuntu-24.04` to an image or a pretty name
colMap = {
    "Test Status": "tests",
    "Date": "date"
}

# these chars are used for saying if tests pass/fail/unknown
testMap = {
    "🔴": "fail",
    "🟢": "pass",
    "⚪": "unknown"
}

def parseMarkdownLink(input):
    """
    Parses a markdown formatted link in the form [name](link)
    and returns a tuple (name, link). If no valid markdown link is found,
    returns (None, None).
    """
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    match = re.search(pattern, input)
    if match:
        return match.group(1), match.group(2)
    return None, None

def parseTableRow(line,cols):
    """
    Take in a line from a table and, using the column names, return a dict 
    containing links to builds
    e.g.
    {
        20210101: {
            "tests": "pass",
            "ubuntu-24.04": {
                "arm64": "https://dufhuwehfuherufhreouhnf",
                "x86_64": "https://sduhfshduifhusdhfuhsudihfu"
            }
        }
    }
    """

    # split colum into cells
    ind0 = line.find("|")
    ind1 = line.rfind("|")
    cells =  [cell.strip() for cell in line[ind0+1:ind1].split("|")]

    # get the date (first column)
    date = int(cells[0])

    # fill the rest in
    out = {}
    for cell,col in zip(cells[1:],cols[1:]):
        if col == "tests":
            out[col] = testMap.get(cell.strip(),"unknown")
        else:
            if cell:
                links = cell.split()
                archlinks = {}
                for link in links:
                    arch,url = parseMarkdownLink(link)
                    if arch:
                        archlinks[arch] = url
                if archlinks:
                    out[col] = archlinks
    if not "tests" in out:
        out["tests"] = "unknown"

    return {date:out}


def parseTable(lines):
    """
    take in the list of lines corresponding to a Markdown table, return a dict
    containing all links
    
    """
    if len(lines) == 0:
        return {}

    # assume the first line has the column names
    colheaders = lines[0]
    colheaders = colheaders[colheaders.find("|")+1:colheaders.rfind("|")]
    cols = [item.strip() for item in colheaders.split("|")]
    cols = [colMap.get(item,item) for item in cols]

    # now we need to parse the rest of the table, assume the first two lines are
    # the column headers and the line below them
    lines = lines[2:]

    # now collect data
    data = {}
    for line in lines:
        data.update(parseTableRow(line,cols))

    return data

def splitPageSections(fname,table):
    """
    splits page into three sections:
    1. before the table section being requested
    2. the section containing the table
    3. lines after the table section
    """
    if not os.path.isfile(fname):
        return [],[],[]

    with open(fname,"r") as f:
        text = f.read()
    lines = text.split("\n")

    # limit to lines between `## {table}` and either the nect section or the end
    use = False
    beforeSection = 0
    afterSection = None
    for i,line in enumerate(lines):
        linemod = line.lower().strip()
        if linemod.startswith("##") and table in linemod:
            use = True
            beforeSection = i
            continue

        # end loop early if we have reached the end of the section        
        if linemod.startswith("#") and use:
            afterSection = i
            break

    # split lines based on indices calculated above
    before = lines[:beforeSection]
    if afterSection is not None:
        section = lines[beforeSection:afterSection]
        after = lines[afterSection:]
    else:
        section = lines[beforeSection:]
        after = []
    
    return before,section,after   

def splitTableSection(lines):
    """
    take the lines from the relevant markdown section and split them into
    before, table, after
    
    assumes that the first table detected is the one we are interested in!
    """
    # map each line to whether they contain part of a table
    hasTable = []
    for line in lines:
        linestrip = line.strip()
        hasTable.append(linestrip.startswith("|"))

    # handle if we don't find any table
    if not any(hasTable):
        return lines,[],[]

    # find the first table index
    tableStart = hasTable.index(True)
    before = lines[:tableStart]

    # find the end of the *first* table in this section 
    if not all(hasTable[tableStart:]):
        tableEnd = hasTable[tableStart:].index(False) + tableStart
        table = lines[tableStart:tableEnd]
        after = lines[tableEnd:]
    else:
        table = lines[tableStart:]
        after = []

    return before,table,after



def tableColumns(cols):

    # map dict keys to column names to actually display
    colMapRev = {v:k for k,v in colMap.items()}
    colNames = [colMapRev.get(col,col) for col in cols]

    line = "| " + " | ".join(colNames) + " |"
    return line

def tableColAlignment(cols):
    """
    return the column alignment line
    """
    return "|:-" + "-:|:-"*(len(cols)-1) + "-:|"

def tableRow(date,data,cols):
    """
    return the table row to be written to the index
    """
    testMapRev = {v:k for k,v in testMap.items()}

    line = f"| {date:08d} | {testMapRev[data.get("tests","unknown")]} | "

    for col in cols:
        if col not in ["date", "tests"]:
            if col in data:
                #format links for builds present
                linkData = data[col]
                linkMarkdowns = []
                for arch,url in linkData.items():
                    linkMarkdowns.append(f"[{arch}]({url})")
                linkMarkdown = " ".join(linkMarkdowns)
                line += f" {linkMarkdown} | "
            else:
                # blank cell for missing builds
                line += "   | "
    return line



def generateTable(data,limit):

    # firstly - limit the dates
    keys = list(data.keys())
    keys = sorted(keys,reverse=True)[:limit]
    data = {k:v for k,v in data.items() if k in keys}

    # now, collect column names
    cols = []
    for date,items in data.items():
        cols.extend(list(items.keys()))
    cols = list(set(cols))

    # order the columns "date", "tests", all of the others in alphabetical order
    sortedCols = ["date", "tests"]
    cols = sorted([col for col in cols if not col in sortedCols])
    cols = sortedCols + cols

    lines = []

    # format columns and alignment
    lines.append(tableColumns(cols))
    lines.append(tableColAlignment(cols))

    # format each date row
    for date in keys:
        lines.append(tableRow(date,data[date],cols))

    return lines



def updateIndex(fname,lines):
    """
    just updates index by overwriting
    """

    text = "\n".join(lines)
    with open(fname,"w") as f:
        f.write(text)
    print(f"Saved {fname}")

def updateTable(table,limit,data):
    """
    Updates a specific table in the daily release page with the latest release links
    
    """
    limit = int(limit)

    # read json data
    data = json.loads(data)
    if isinstance(data, str):
        data = json.loads(data)

    # repackage it to match format of table data
    rowdata = data["packages"]
    rowdata["tests"] = data.get("tests","unknown")
    data = {data["date"]: rowdata}
    

    # this is the file to update
    fname = "index.md"

    # read theindex in and split by relevant section
    beforeSection,tableSection,afterSection = splitPageSections(fname,table)
    
    # split section into lines before, including and after table
    beforeTable,tableLines,afterTable = splitTableSection(tableSection)

    # parse the table
    tabledata = parseTable(tableLines)

    # update with the new data
    tabledata.update(data)

    # generate new markdown table
    newtable = generateTable(tabledata,limit)

    # recombine markdown lines
    lines = beforeSection + beforeTable + newtable + afterTable + afterSection
    print(len(beforeSection))

    # update index
    updateIndex(fname,lines)


def main():
    parser = argparse.ArgumentParser(description="Update memgraph/mage daily release tables")
    
    # Define required arguments
    parser.add_argument('table', help='Table name: "memgraph"|"mage"')
    parser.add_argument('limit', help='Maximum number of builds to retain (42)')
    parser.add_argument('data', help='JSON data from build workflow')
    
    args = parser.parse_args()
    
    # print the provided arguments for debugging
    print("Table:", args.table)
    print("Limit:", args.limit)
    print("Data:", args.data)
    
    updateTable(args.table,args.limit,args.data)

if __name__ == "__main__":
    main()